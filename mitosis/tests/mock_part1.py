from logging import getLogger

import numpy as np
from numpy.typing import NBitBase
from numpy.typing import NDArray


class Klass:
    @staticmethod
    def gen_data(length: int) -> dict[str, NDArray[np.floating[NBitBase]]]:
        getLogger(__name__).info("This is run every time")
        getLogger(__name__).debug("This is run in debug mode only")

        return {"data": np.ones(length, dtype=np.float_)}
