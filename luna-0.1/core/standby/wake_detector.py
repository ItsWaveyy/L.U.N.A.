import asyncio

from livekit.wakeword import WakeWordListener, WakeWordModel


MODEL_PATH = "output/hey_luna/hey_luna.onnx"


class WakeDetector:
    def __init__(
        self,
        model_path: str = MODEL_PATH,
        threshold: float = 0.90,
        debounce: float = 2.0,
    ):
        self.model = WakeWordModel(
            models=[model_path]
        )

        self.listener = WakeWordListener(
            self.model,
            threshold=threshold,
            debounce=debounce,
        )

    async def wait_for_wake(self):
        async with self.listener:
            while True:
                detection = await self.listener.wait_for_detection()

                if detection is None:
                    continue

                return detection