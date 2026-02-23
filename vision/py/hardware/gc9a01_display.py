from __future__ import annotations

from dataclasses import dataclass

from vision.py.assets import config
from vision.py.engine import shapes
from vision.py.engine.render_engine import FramePlan
from vision.py.hardware import blit
from vision.py.hardware import display as display_mod

try:
    import numpy as np
except ImportError:  # pragma: no cover (Pi runtime)
    np = None


@dataclass
class GC9A01_Display:
    swap_left_right: bool = False

    def __post_init__(self) -> None:
        self.left_eye: object | None = None
        self.right_eye: object | None = None

    def init_displays(self) -> None:
        left, right = display_mod.init_displays(swap_left_right=self.swap_left_right)
        self.left_eye, self.right_eye = left, right

    def is_ready(self) -> bool:
        return not (self.left_eye is None and self.right_eye is None)

    def restart_displays(self) -> bool:
        try:
            self.init_displays()
        except Exception:
            return False
        return self.left_eye is not None and self.right_eye is not None

    def _apply_eye_shape_left(self, frame: object | None) -> object | None:
        if frame is None:
            return frame
        assert np is not None  # NumPy required for shape masking
        arr = np.array(frame, dtype=np.uint8)
        masked_arr = shapes.apply_shape_mask_numpy(arr, config.get_eye_shape(), mirror=False)
        assert masked_arr is not None
        from PIL import Image

        return Image.fromarray(masked_arr.copy())

    def _apply_eye_shape_right(self, frame: object | None) -> object | None:
        if frame is None:
            return frame
        assert np is not None
        arr = np.array(frame, dtype=np.uint8)
        masked_arr = shapes.apply_shape_mask_numpy(arr, config.get_eye_shape(), mirror=True)
        assert masked_arr is not None
        from PIL import Image

        return Image.fromarray(masked_arr.copy())

    def blit(
        self,
        plan: FramePlan,
        *,
        inside_out: bool = False,
        outside_in: bool = False,
        sync: bool = False,
    ) -> None:
        if not self.is_ready():
            return
        left_img = plan.left
        right_img = plan.right
        if left_img is None:
            return

        if sync:
            blit.blit_pil_to_both(
                self.left_eye,
                self.right_eye,
                self._apply_eye_shape_left(left_img),
                self._apply_eye_shape_right(right_img),
                reverse_rows=False,
                outside_in=outside_in,
                inside_out=inside_out,
                partial_rows=None,
            )
        else:
            blit.blit_pil_to_both_async(
                self.left_eye,
                self.right_eye,
                self._apply_eye_shape_left(left_img),
                self._apply_eye_shape_right(right_img),
                outside_in=outside_in,
                inside_out=inside_out,
            )
