"""ScanSOLO GPR Engine — modular, testável, sem GPRPy."""

from gpr_engine._types import DZTData
from gpr_engine.reader import DZTReader, DZTReadError

__version__ = "0.1.0"
__all__ = ["DZTData", "DZTReader", "DZTReadError"]
