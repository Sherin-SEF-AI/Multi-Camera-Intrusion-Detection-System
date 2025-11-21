"""
Video Recorder Utility
Handles video recording with H.264/H.265 encoding.
"""

import cv2
import threading
from queue import Queue, Empty
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
import numpy as np
import time

from app.utils.logger import get_logger

logger = get_logger(__name__)


class VideoRecorder:
    """
    Video recorder with background thread for non-blocking recording.

    Supports multiple codecs and quality settings.
    """

    def __init__(
        self,
        output_path: str,
        fps: int = 30,
        resolution: Optional[Tuple[int, int]] = None,
        codec: str = 'h264',
        quality: str = 'medium'
    ):
        """
        Initialize video recorder.

        Args:
            output_path: Path to output video file
            fps: Frames per second
            resolution: Video resolution (width, height). Auto-detect if None.
            codec: Video codec ('h264', 'h265', 'mjpeg')
            quality: Quality preset ('low', 'medium', 'high')
        """
        self.output_path = Path(output_path)
        self.fps = fps
        self.resolution = resolution
        self.codec = codec
        self.quality = quality

        # Create output directory
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # VideoWriter
        self.writer: Optional[cv2.VideoWriter] = None
        self.is_recording = False

        # Frame queue for asynchronous writing
        self.frame_queue: Queue = Queue(maxsize=300)
        self.recording_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        # Statistics
        self.frame_count = 0
        self.dropped_frames = 0
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def _get_fourcc(self) -> int:
        """
        Get FourCC code for video codec.

        Returns:
            FourCC code
        """
        codec_map = {
            'h264': 'avc1',  # H.264
            'h265': 'hev1',  # H.265
            'mjpeg': 'MJPG',  # Motion JPEG
            'xvid': 'XVID',  # Xvid
            'mp4v': 'mp4v'   # MPEG-4
        }

        codec_str = codec_map.get(self.codec.lower(), 'avc1')
        return cv2.VideoWriter_fourcc(*codec_str)

    def start(self, first_frame: Optional[np.ndarray] = None) -> bool:
        """
        Start recording.

        Args:
            first_frame: First frame to determine resolution if not specified

        Returns:
            True if started successfully
        """
        if self.is_recording:
            logger.warning("Recording already in progress")
            return False

        try:
            # Determine resolution from first frame if not specified
            if self.resolution is None:
                if first_frame is None:
                    raise ValueError("Resolution must be specified or first_frame provided")
                height, width = first_frame.shape[:2]
                self.resolution = (width, height)

            # Create VideoWriter
            fourcc = self._get_fourcc()
            self.writer = cv2.VideoWriter(
                str(self.output_path),
                fourcc,
                self.fps,
                self.resolution
            )

            if not self.writer.isOpened():
                raise RuntimeError("Failed to open VideoWriter")

            # Start recording thread
            self.stop_event.clear()
            self.recording_thread = threading.Thread(
                target=self._recording_loop,
                name="VideoRecorderThread",
                daemon=True
            )
            self.recording_thread.start()

            self.is_recording = True
            self.start_time = time.time()
            self.frame_count = 0
            self.dropped_frames = 0

            logger.info(f"Started recording to {self.output_path}")

            # Write first frame if provided
            if first_frame is not None:
                self.write_frame(first_frame)

            return True

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            return False

    def write_frame(self, frame: np.ndarray) -> bool:
        """
        Write frame to video (non-blocking).

        Args:
            frame: Frame to write

        Returns:
            True if frame queued successfully
        """
        if not self.is_recording:
            return False

        try:
            # Resize frame if needed
            if frame.shape[1] != self.resolution[0] or frame.shape[0] != self.resolution[1]:
                frame = cv2.resize(frame, self.resolution)

            # Try to add to queue
            self.frame_queue.put_nowait(frame.copy())
            return True

        except:
            # Queue full - drop frame
            self.dropped_frames += 1
            return False

    def _recording_loop(self):
        """Background thread for writing frames."""
        logger.info("Recording loop started")

        while not self.stop_event.is_set() or not self.frame_queue.empty():
            try:
                # Get frame from queue with timeout
                frame = self.frame_queue.get(timeout=0.1)

                # Write frame
                if self.writer is not None:
                    self.writer.write(frame)
                    self.frame_count += 1

            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error writing frame: {e}")

        logger.info("Recording loop ended")

    def stop(self) -> dict:
        """
        Stop recording and close video file.

        Returns:
            Recording statistics dictionary
        """
        if not self.is_recording:
            return {}

        # Signal stop
        self.stop_event.set()

        # Wait for thread to finish
        if self.recording_thread is not None:
            self.recording_thread.join(timeout=5.0)

        # Release writer
        if self.writer is not None:
            self.writer.release()
            self.writer = None

        self.is_recording = False
        self.end_time = time.time()

        # Calculate statistics
        duration = self.end_time - self.start_time if self.start_time else 0
        file_size = self.output_path.stat().st_size if self.output_path.exists() else 0

        stats = {
            'output_path': str(self.output_path),
            'frame_count': self.frame_count,
            'dropped_frames': self.dropped_frames,
            'duration': duration,
            'fps': self.fps,
            'resolution': self.resolution,
            'file_size_mb': file_size / (1024 * 1024),
            'codec': self.codec
        }

        logger.info(f"Stopped recording. Stats: {stats}")

        return stats

    def is_active(self) -> bool:
        """
        Check if recording is active.

        Returns:
            True if recording
        """
        return self.is_recording

    def get_stats(self) -> dict:
        """
        Get current recording statistics.

        Returns:
            Statistics dictionary
        """
        duration = (time.time() - self.start_time) if self.start_time else 0

        return {
            'is_recording': self.is_recording,
            'frame_count': self.frame_count,
            'dropped_frames': self.dropped_frames,
            'duration': duration,
            'queue_size': self.frame_queue.qsize(),
            'fps': self.fps
        }


class EventRecorder:
    """
    Event-triggered recorder that records before and after events.

    Maintains a circular buffer for pre-event recording.
    """

    def __init__(
        self,
        output_dir: str,
        fps: int = 15,
        pre_event_duration: int = 10,
        post_event_duration: int = 30,
        codec: str = 'h264'
    ):
        """
        Initialize event recorder.

        Args:
            output_dir: Directory for output videos
            fps: Frames per second
            pre_event_duration: Seconds to record before event
            post_event_duration: Seconds to record after event
            codec: Video codec
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.fps = fps
        self.pre_event_duration = pre_event_duration
        self.post_event_duration = post_event_duration
        self.codec = codec

        # Circular buffer for pre-event frames
        self.buffer_size = int(fps * pre_event_duration)
        self.frame_buffer: Queue = Queue(maxsize=self.buffer_size)

        # Current recorder
        self.recorder: Optional[VideoRecorder] = None
        self.is_recording_event = False
        self.event_start_time: Optional[float] = None

        logger.info("Event Recorder initialized")

    def add_frame(self, frame: np.ndarray):
        """
        Add frame to buffer.

        Args:
            frame: Frame to add
        """
        # Add to circular buffer
        if self.frame_buffer.full():
            try:
                self.frame_buffer.get_nowait()
            except Empty:
                pass

        self.frame_buffer.put(frame.copy())

        # If recording event, write frame
        if self.is_recording_event and self.recorder is not None:
            self.recorder.write_frame(frame)

            # Check if post-event duration elapsed
            elapsed = time.time() - self.event_start_time
            if elapsed >= self.post_event_duration:
                self.stop_event_recording()

    def trigger_event(
        self,
        event_id: str,
        camera_id: int,
        resolution: Tuple[int, int]
    ) -> Optional[str]:
        """
        Trigger event recording.

        Args:
            event_id: Unique event identifier
            camera_id: Camera ID
            resolution: Video resolution

        Returns:
            Output video path or None if failed
        """
        if self.is_recording_event:
            logger.warning("Event recording already in progress")
            return None

        try:
            # Generate output filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"event_{camera_id}_{event_id}_{timestamp}.mp4"
            output_path = self.output_dir / output_filename

            # Create recorder
            self.recorder = VideoRecorder(
                output_path=str(output_path),
                fps=self.fps,
                resolution=resolution,
                codec=self.codec
            )

            # Start recording
            if not self.recorder.start():
                return None

            # Write buffered frames (pre-event)
            frames = []
            while not self.frame_buffer.empty():
                try:
                    frames.append(self.frame_buffer.get_nowait())
                except Empty:
                    break

            for frame in frames:
                self.recorder.write_frame(frame)

            self.is_recording_event = True
            self.event_start_time = time.time()

            logger.info(f"Event recording started: {output_path}")

            return str(output_path)

        except Exception as e:
            logger.error(f"Failed to trigger event recording: {e}")
            return None

    def stop_event_recording(self) -> Optional[dict]:
        """
        Stop event recording.

        Returns:
            Recording statistics or None
        """
        if not self.is_recording_event or self.recorder is None:
            return None

        stats = self.recorder.stop()
        self.recorder = None
        self.is_recording_event = False
        self.event_start_time = None

        logger.info("Event recording stopped")

        return stats


if __name__ == "__main__":
    # Test video recorder
    output_path = "test_recording.mp4"
    recorder = VideoRecorder(output_path, fps=30, resolution=(640, 480))

    # Create test frames
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    if recorder.start(test_frame):
        print("Recording started")

        for i in range(90):  # 3 seconds at 30 fps
            # Create frame with frame number
            frame = test_frame.copy()
            cv2.putText(frame, f"Frame {i}", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 2)
            recorder.write_frame(frame)
            time.sleep(1/30)

        stats = recorder.stop()
        print(f"Recording stopped. Stats: {stats}")
