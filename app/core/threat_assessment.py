"""
Threat Assessment Engine
Multi-factor risk scoring and threat level determination.
"""

from typing import Dict, Optional, Tuple
from datetime import datetime, time as dt_time
from dataclasses import dataclass

from app.database.models import Person, AuthorizationLevel, Event, Severity
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ThreatScore:
    """Threat assessment result."""
    total_score: int  # 0-100
    level: str  # low, medium, high, critical
    severity: Severity
    factors: Dict[str, float]
    description: str


class ThreatAssessment:
    """
    Multi-factor threat assessment engine.

    Calculates risk scores based on:
    - Identity/Authorization status
    - Behavioral anomalies
    - Location/Zone criticality
    - Time of day
    - Trajectory abnormality
    - Dwell time
    - Group size
    - Historical incidents
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize threat assessment engine.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        threat_config = self.config.get('threat', {})

        # Risk score weights (should sum to 1.0)
        weights = threat_config.get('weights', {})
        self.weight_identity = weights.get('identity_status', 0.30)
        self.weight_behavior = weights.get('behavior_anomaly', 0.25)
        self.weight_location = weights.get('location_criticality', 0.20)
        self.weight_time = weights.get('time_factor', 0.10)
        self.weight_trajectory = weights.get('trajectory_abnormality', 0.10)
        self.weight_dwell = weights.get('dwell_time', 0.05)

        # Threat levels
        levels = threat_config.get('levels', {})
        self.level_low = levels.get('low', [0, 25])
        self.level_medium = levels.get('medium', [26, 50])
        self.level_high = levels.get('high', [51, 75])
        self.level_critical = levels.get('critical', [76, 100])

        logger.info("Threat Assessment Engine initialized")

    def assess_threat(
        self,
        person: Optional[Person] = None,
        person_auth_level: Optional[AuthorizationLevel] = None,
        behavior_anomaly_score: float = 0.0,
        zone_criticality: float = 0.0,
        trajectory_abnormal: bool = False,
        dwell_time_seconds: float = 0.0,
        group_size: int = 1,
        time_of_day: Optional[datetime] = None,
        previous_incidents: int = 0
    ) -> ThreatScore:
        """
        Assess threat level based on multiple factors.

        Args:
            person: Person object (if identified)
            person_auth_level: Authorization level (if person not in DB)
            behavior_anomaly_score: Behavioral anomaly score (0.0-1.0)
            zone_criticality: Zone criticality level (0.0-1.0)
            trajectory_abnormal: Whether trajectory is abnormal
            dwell_time_seconds: Time spent in area (seconds)
            group_size: Number of persons in group
            time_of_day: Current time
            previous_incidents: Number of previous incidents

        Returns:
            ThreatScore object with assessment results
        """
        factors = {}

        # Factor 1: Identity Status (0-60 points)
        identity_score = self._assess_identity(person, person_auth_level)
        factors['identity'] = identity_score

        # Factor 2: Behavior Anomaly (0-40 points)
        behavior_score = behavior_anomaly_score * 40.0
        factors['behavior'] = behavior_score

        # Factor 3: Location Criticality (0-30 points)
        location_score = zone_criticality * 30.0
        factors['location'] = location_score

        # Factor 4: Time of Day Factor (0-20 points)
        time_score = self._assess_time_factor(time_of_day)
        factors['time'] = time_score

        # Factor 5: Trajectory Abnormality (0-20 points)
        trajectory_score = 20.0 if trajectory_abnormal else 0.0
        factors['trajectory'] = trajectory_score

        # Factor 6: Dwell Time (0-15 points)
        dwell_score = self._assess_dwell_time(dwell_time_seconds)
        factors['dwell_time'] = dwell_score

        # Factor 7: Group Size (0-15 points)
        group_score = self._assess_group_size(group_size)
        factors['group_size'] = group_score

        # Factor 8: Previous Incidents (0-25 points)
        history_score = min(previous_incidents * 5.0, 25.0)
        factors['history'] = history_score

        # Calculate weighted total score
        total_score = (
            identity_score * self.weight_identity +
            behavior_score * self.weight_behavior +
            location_score * self.weight_location +
            time_score * self.weight_time +
            trajectory_score * self.weight_trajectory +
            dwell_score * self.weight_dwell
        )

        # Add bonus factors (not weighted, added directly)
        total_score += min(group_score + history_score, 25.0)

        # Clamp to 0-100
        total_score = max(0, min(100, int(total_score)))

        # Determine threat level
        level, severity = self._determine_level(total_score)

        # Generate description
        description = self._generate_description(total_score, factors, person)

        return ThreatScore(
            total_score=total_score,
            level=level,
            severity=severity,
            factors=factors,
            description=description
        )

    def _assess_identity(
        self,
        person: Optional[Person],
        auth_level: Optional[AuthorizationLevel]
    ) -> float:
        """
        Assess identity threat factor.

        Returns:
            Score (0-60)
        """
        if person:
            auth_level = person.authorization_level

        if auth_level == AuthorizationLevel.BLACKLIST:
            return 60.0  # Maximum threat
        elif auth_level == AuthorizationLevel.UNKNOWN:
            return 30.0  # Medium threat
        elif auth_level == AuthorizationLevel.VISITOR:
            return 15.0  # Low-medium threat
        elif auth_level == AuthorizationLevel.AUTHORIZED:
            return 0.0  # No threat from identity
        else:
            return 30.0  # Unknown = medium threat

    def _assess_time_factor(self, time_of_day: Optional[datetime]) -> float:
        """
        Assess time-of-day threat factor.

        Higher risk during:
        - Late night (22:00 - 06:00)
        - Early morning (06:00 - 08:00)
        - After hours (17:00 - 22:00) for office buildings

        Returns:
            Score (0-20)
        """
        if not time_of_day:
            time_of_day = datetime.now()

        hour = time_of_day.hour

        # Late night / early morning (22:00 - 06:00)
        if hour >= 22 or hour < 6:
            return 20.0  # High risk

        # Early morning (06:00 - 08:00)
        elif 6 <= hour < 8:
            return 10.0  # Medium risk

        # After hours (17:00 - 22:00)
        elif 17 <= hour < 22:
            return 15.0  # Medium-high risk

        # Business hours (08:00 - 17:00)
        else:
            return 0.0  # Normal hours

    def _assess_dwell_time(self, dwell_time_seconds: float) -> float:
        """
        Assess dwell time threat factor.

        Longer dwell time in sensitive areas = higher risk

        Returns:
            Score (0-15)
        """
        if dwell_time_seconds < 30:
            return 0.0  # Normal passage
        elif dwell_time_seconds < 60:
            return 5.0  # Slight concern
        elif dwell_time_seconds < 120:
            return 10.0  # Loitering
        else:
            return 15.0  # Prolonged loitering

    def _assess_group_size(self, group_size: int) -> float:
        """
        Assess group size threat factor.

        Larger groups may indicate higher risk

        Returns:
            Score (0-15)
        """
        if group_size == 1:
            return 0.0
        elif group_size == 2:
            return 3.0
        elif group_size <= 4:
            return 7.0
        elif group_size <= 6:
            return 12.0
        else:
            return 15.0  # Large group

    def _determine_level(self, score: int) -> Tuple[str, Severity]:
        """
        Determine threat level from score.

        Args:
            score: Threat score (0-100)

        Returns:
            Tuple of (level_name, Severity enum)
        """
        if score >= self.level_critical[0]:
            return ("critical", Severity.CRITICAL)
        elif score >= self.level_high[0]:
            return ("high", Severity.HIGH)
        elif score >= self.level_medium[0]:
            return ("medium", Severity.MEDIUM)
        else:
            return ("low", Severity.LOW)

    def _generate_description(
        self,
        score: int,
        factors: Dict[str, float],
        person: Optional[Person]
    ) -> str:
        """
        Generate human-readable threat description.

        Args:
            score: Total threat score
            factors: Individual factor scores
            person: Person object if identified

        Returns:
            Threat description string
        """
        # Start with score
        desc_parts = [f"Threat Score: {score}/100"]

        # Primary factors
        if factors.get('identity', 0) > 30:
            if person and person.authorization_level == AuthorizationLevel.BLACKLIST:
                desc_parts.append("BLACKLISTED INDIVIDUAL")
            else:
                desc_parts.append("Unknown/Unauthorized person")

        if factors.get('behavior', 0) > 20:
            desc_parts.append("Abnormal behavior detected")

        if factors.get('location', 0) > 15:
            desc_parts.append("In restricted/critical area")

        if factors.get('time', 0) > 10:
            desc_parts.append("After-hours activity")

        if factors.get('trajectory', 0) > 0:
            desc_parts.append("Unusual movement pattern")

        if factors.get('dwell_time', 0) > 5:
            desc_parts.append("Loitering detected")

        if factors.get('group_size', 0) > 7:
            desc_parts.append("Large group detected")

        if factors.get('history', 0) > 0:
            desc_parts.append("Previous incident history")

        return " | ".join(desc_parts)


if __name__ == "__main__":
    # Test threat assessment
    config = {
        'threat': {
            'weights': {
                'identity_status': 0.30,
                'behavior_anomaly': 0.25,
                'location_criticality': 0.20,
                'time_factor': 0.10,
                'trajectory_abnormality': 0.10,
                'dwell_time': 0.05
            },
            'levels': {
                'low': [0, 25],
                'medium': [26, 50],
                'high': [51, 75],
                'critical': [76, 100]
            }
        }
    }

    assessor = ThreatAssessment(config)

    # Test cases
    print("Test 1: Authorized person during business hours")
    result = assessor.assess_threat(
        person_auth_level=AuthorizationLevel.AUTHORIZED,
        behavior_anomaly_score=0.1,
        zone_criticality=0.3,
        time_of_day=datetime(2024, 1, 1, 14, 30)
    )
    print(f"Score: {result.total_score}, Level: {result.level}")
    print(f"Description: {result.description}\n")

    print("Test 2: Unknown person in restricted area after hours")
    result = assessor.assess_threat(
        person_auth_level=AuthorizationLevel.UNKNOWN,
        behavior_anomaly_score=0.6,
        zone_criticality=0.9,
        trajectory_abnormal=True,
        dwell_time_seconds=150,
        time_of_day=datetime(2024, 1, 1, 23, 30)
    )
    print(f"Score: {result.total_score}, Level: {result.level}")
    print(f"Description: {result.description}\n")

    print("Test 3: Blacklisted person")
    result = assessor.assess_threat(
        person_auth_level=AuthorizationLevel.BLACKLIST,
        behavior_anomaly_score=0.8,
        zone_criticality=0.7,
        previous_incidents=2
    )
    print(f"Score: {result.total_score}, Level: {result.level}")
    print(f"Description: {result.description}")
