"""
Person Re-Identification (ReID) Engine
Deep learning-based person matching across cameras using feature extraction.
"""

import torch
import torch.nn as nn
import torchvision.transforms as transforms
import numpy as np
from typing import Optional, List, Tuple, Dict
from pathlib import Path
import cv2
from sklearn.metrics.pairwise import cosine_similarity, euclidean_distances
import pickle

from app.utils.logger import get_logger

logger = get_logger(__name__)


class FeatureExtractor(nn.Module):
    """
    Lightweight CNN for feature extraction.
    Uses ResNet-50 backbone pretrained on ImageNet.
    """

    def __init__(self, feature_dim: int = 512):
        """
        Initialize feature extractor.

        Args:
            feature_dim: Output feature dimension
        """
        super().__init__()

        # Use pretrained ResNet-50 as backbone
        import torchvision.models as models
        resnet = models.resnet50(pretrained=True)

        # Remove final FC layer
        self.backbone = nn.Sequential(*list(resnet.children())[:-1])

        # Add custom embedding layer
        self.embedding = nn.Sequential(
            nn.Linear(2048, feature_dim),
            nn.BatchNorm1d(feature_dim),
            nn.ReLU()
        )

        logger.info(f"Feature extractor initialized (dim={feature_dim})")

    def forward(self, x):
        """Forward pass."""
        x = self.backbone(x)
        x = x.view(x.size(0), -1)
        x = self.embedding(x)
        # L2 normalize
        x = nn.functional.normalize(x, p=2, dim=1)
        return x


class PersonReID:
    """
    Person Re-Identification engine.

    Features:
    - Deep learning feature extraction
    - Cross-camera matching
    - Gallery management
    - Similarity scoring
    - Quality-aware matching
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize ReID engine.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        reid_config = self.config.get('reid', {})

        self.enabled = reid_config.get('enabled', True)
        self.feature_dim = reid_config.get('feature_dim', 512)
        self.similarity_threshold = reid_config.get('similarity_threshold', 0.6)
        self.device = reid_config.get('device', 'cuda' if torch.cuda.is_available() else 'cpu')
        self.min_quality_score = reid_config.get('min_quality_score', 0.3)

        # Feature extractor model
        self.model: Optional[nn.Module] = None

        # Image preprocessing
        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((256, 128)),  # Standard ReID size
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

        # Gallery of known persons (person_id -> feature vectors)
        self.gallery: Dict[int, List[np.ndarray]] = {}

        # Feature cache for current frame (track_id -> feature)
        self.track_features: Dict[int, np.ndarray] = {}

        # Statistics
        self.total_extractions = 0
        self.total_matches = 0

        if self.enabled:
            self._initialize_model()

        logger.info(f"Person ReID initialized (enabled={self.enabled}, device={self.device})")

    def _initialize_model(self):
        """Initialize the ReID model."""
        try:
            self.model = FeatureExtractor(feature_dim=self.feature_dim)
            self.model.to(self.device)
            self.model.eval()

            logger.info("ReID model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to initialize ReID model: {e}")
            self.enabled = False

    def extract_features(
        self,
        frame: np.ndarray,
        bbox: Tuple[int, int, int, int],
        quality_check: bool = True
    ) -> Optional[np.ndarray]:
        """
        Extract feature vector from person crop.

        Args:
            frame: Full frame (BGR)
            bbox: Bounding box (x, y, w, h)
            quality_check: Whether to check image quality

        Returns:
            Feature vector (normalized) or None
        """
        if not self.enabled or self.model is None:
            return None

        try:
            x, y, w, h = bbox

            # Extract person region
            person_img = frame[y:y+h, x:x+w]

            if person_img.size == 0 or w < 20 or h < 40:
                return None

            # Quality check
            if quality_check:
                quality = self._assess_quality(person_img)
                if quality < self.min_quality_score:
                    logger.debug(f"Low quality image rejected: {quality:.2f}")
                    return None

            # Convert BGR to RGB
            person_img_rgb = cv2.cvtColor(person_img, cv2.COLOR_BGR2RGB)

            # Preprocess
            img_tensor = self.transform(person_img_rgb)
            img_tensor = img_tensor.unsqueeze(0).to(self.device)

            # Extract features
            with torch.no_grad():
                features = self.model(img_tensor)

            # Convert to numpy
            features_np = features.cpu().numpy().flatten()

            self.total_extractions += 1

            return features_np

        except Exception as e:
            logger.error(f"Feature extraction error: {e}")
            return None

    def _assess_quality(self, img: np.ndarray) -> float:
        """
        Assess image quality for ReID.

        Checks:
        - Sharpness (Laplacian variance)
        - Brightness
        - Size

        Args:
            img: Person crop image

        Returns:
            Quality score (0.0 - 1.0)
        """
        # Check size
        h, w = img.shape[:2]
        if h < 40 or w < 20:
            return 0.0

        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Sharpness (Laplacian variance)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        sharpness = laplacian.var()
        sharpness_score = min(sharpness / 1000.0, 1.0)  # Normalize

        # Brightness
        brightness = gray.mean()
        brightness_score = 1.0 - abs(brightness - 127.5) / 127.5  # Optimal at mid-range

        # Combined score
        quality = (sharpness_score * 0.7 + brightness_score * 0.3)

        return quality

    def add_to_gallery(self, person_id: int, features: np.ndarray):
        """
        Add feature vector to gallery for a person.

        Args:
            person_id: Person ID
            features: Feature vector
        """
        if person_id not in self.gallery:
            self.gallery[person_id] = []

        self.gallery[person_id].append(features)

        # Keep only last 10 features per person
        if len(self.gallery[person_id]) > 10:
            self.gallery[person_id] = self.gallery[person_id][-10:]

        logger.debug(f"Added features to gallery for person {person_id}")

    def match_to_gallery(
        self,
        features: np.ndarray,
        top_k: int = 5,
        metric: str = 'cosine'
    ) -> List[Tuple[int, float]]:
        """
        Match feature vector against gallery.

        Args:
            features: Query feature vector
            top_k: Return top K matches
            metric: Distance metric ('cosine' or 'euclidean')

        Returns:
            List of (person_id, similarity_score) tuples, sorted by score
        """
        if not self.gallery:
            return []

        matches = []

        for person_id, person_features in self.gallery.items():
            # Compute similarity with all features for this person
            if metric == 'cosine':
                # Cosine similarity (higher = more similar)
                similarities = cosine_similarity(
                    features.reshape(1, -1),
                    np.array(person_features)
                ).flatten()
                max_similarity = similarities.max()
            else:
                # Euclidean distance (lower = more similar)
                distances = euclidean_distances(
                    features.reshape(1, -1),
                    np.array(person_features)
                ).flatten()
                max_similarity = 1.0 / (1.0 + distances.min())  # Convert to similarity

            matches.append((person_id, max_similarity))

        # Sort by similarity (descending)
        matches.sort(key=lambda x: x[1], reverse=True)

        self.total_matches += 1

        return matches[:top_k]

    def identify_person(
        self,
        frame: np.ndarray,
        bbox: Tuple[int, int, int, int],
        track_id: Optional[int] = None
    ) -> Optional[Tuple[int, float]]:
        """
        Identify person in frame against gallery.

        Args:
            frame: Full frame
            bbox: Bounding box
            track_id: Track ID (for caching)

        Returns:
            (person_id, confidence) or None
        """
        # Check cache first
        if track_id is not None and track_id in self.track_features:
            features = self.track_features[track_id]
        else:
            # Extract features
            features = self.extract_features(frame, bbox)

            if features is None:
                return None

            # Cache features
            if track_id is not None:
                self.track_features[track_id] = features

        # Match against gallery
        matches = self.match_to_gallery(features, top_k=1)

        if not matches:
            return None

        person_id, similarity = matches[0]

        # Check threshold
        if similarity >= self.similarity_threshold:
            logger.info(f"Person identified: ID {person_id} (confidence: {similarity:.2f})")
            return (person_id, similarity)

        return None

    def update_track_feature(
        self,
        track_id: int,
        frame: np.ndarray,
        bbox: Tuple[int, int, int, int]
    ):
        """
        Update feature cache for a track.

        Args:
            track_id: Track ID
            frame: Current frame
            bbox: Bounding box
        """
        features = self.extract_features(frame, bbox)

        if features is not None:
            self.track_features[track_id] = features

    def clear_track_cache(self, track_id: int):
        """
        Clear cached features for a track.

        Args:
            track_id: Track ID
        """
        self.track_features.pop(track_id, None)

    def save_gallery(self, path: str):
        """
        Save gallery to disk.

        Args:
            path: File path to save
        """
        try:
            with open(path, 'wb') as f:
                pickle.dump(self.gallery, f)

            logger.info(f"Gallery saved to {path} ({len(self.gallery)} persons)")

        except Exception as e:
            logger.error(f"Failed to save gallery: {e}")

    def load_gallery(self, path: str):
        """
        Load gallery from disk.

        Args:
            path: File path to load
        """
        try:
            if not Path(path).exists():
                logger.warning(f"Gallery file not found: {path}")
                return

            with open(path, 'rb') as f:
                self.gallery = pickle.load(f)

            logger.info(f"Gallery loaded from {path} ({len(self.gallery)} persons)")

        except Exception as e:
            logger.error(f"Failed to load gallery: {e}")

    def get_statistics(self) -> Dict:
        """
        Get ReID statistics.

        Returns:
            Statistics dictionary
        """
        return {
            'enabled': self.enabled,
            'gallery_size': len(self.gallery),
            'total_persons': sum(len(features) for features in self.gallery.values()),
            'total_extractions': self.total_extractions,
            'total_matches': self.total_matches,
            'cached_tracks': len(self.track_features),
            'device': self.device,
            'feature_dim': self.feature_dim
        }


if __name__ == "__main__":
    # Test ReID engine
    config = {
        'reid': {
            'enabled': True,
            'feature_dim': 512,
            'similarity_threshold': 0.6,
            'device': 'cuda',
            'min_quality_score': 0.3
        }
    }

    reid = PersonReID(config)

    # Create test images
    test_img = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    bbox = (100, 100, 80, 160)

    # Extract features
    print("Extracting features...")
    features = reid.extract_features(test_img, bbox)

    if features is not None:
        print(f"Features shape: {features.shape}")
        print(f"Feature norm: {np.linalg.norm(features):.4f}")

        # Add to gallery
        reid.add_to_gallery(person_id=1, features=features)

        # Try to match
        matches = reid.match_to_gallery(features, top_k=5)
        print(f"Matches: {matches}")

        # Statistics
        stats = reid.get_statistics()
        print(f"Statistics: {stats}")

    print("Test complete")
