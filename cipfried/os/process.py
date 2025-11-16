from cipfried.os.memory import Memory
from cipfried.os.video import Video, VideoStream


class Process:
    def __init__(self, memory: Memory, video: Video):
        self._memory = memory
        self._video = video

        self.name = 'Tibia'
        self.pid = None

    def hook(self,) -> None:
        self.pid = self._memory.get_pid_by_name(self.name)


    def capture_video(self) -> VideoStream:
        if self._video.is_running():
            return self._video.stream

        self._video.start()

        return self._video.stream

    def abort_video_capture(self) -> None:
        self._video.stop()