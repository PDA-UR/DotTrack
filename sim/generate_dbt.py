# import os  # TODO export filenames as absolute paths
from torus import Torus
import numpy as np
from skimage import io
from enum import Enum, auto


class TorusGenerator(object):
    """Records and saves pertinent data of de Bruijn torus generation."""

    def __init__(self, w, h, win_w, win_h, base_fname="output-"):
        """Set dimensions of final de Bruijn torus.

        :w: Width of final de Bruijn torus.
        :h: Height of final de Bruijn torus.
        :win_w: Window width of de Bruijn torus.
        :win_h: Window height of de Bruijn torus.
        :base_fname: Base file name to save the de Bruijn tori to. Full name
        will be base_fname + "{w}x{h}_{win_w}x{win_h}.png".
        """
        self._s = w
        self._r = h
        self._n = win_w
        self._m = win_h
        self._base_fname = base_fname

        if self._r == self._s == 256 and self._m == self._n == 4:
            self._generate_256x256_4x4_dbt()
            pass
        elif self._r == 4096 and self._s == 8192 and self._m == self._n == 5:
            self._generate_8192x4096_5x5_dbt()
            pass
        else:
            err_msg = "Dimensions not possible or not supported yet."
            raise ValueError(err_msg)

    # def _init_generation(self):
    #     self.constr_log = DBTConstructionLog()
    #     src_dbt = [
    #         [0, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0, 1, 1, 1],
    #         [0, 0, 1, 1, 0, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 1],
    #         [0, 0, 1, 1, 0, 1, 1, 1, 0, 0, 1, 1, 0, 0, 1, 0],
    #         [1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1, 1, 0, 1, 1],
    #     ]
    #     src_dbt = np.array(src_dbt, dtype=np.uint8) * 255
    #     m, n = 3, 2
    #     torus = Torus(src_dbt, m, n, "storage.txt")
    #     torus.transpose()
    #     src_dbt = src_dbt.transpose()

    def _generate_256x256_4x4_dbt(self):
        # self._init_generation()

        # values = [
        #     [0, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0, 1, 1, 1],
        #     [0, 0, 1, 1, 0, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 1],
        #     [0, 0, 1, 1, 0, 1, 1, 1, 0, 0, 1, 1, 0, 0, 1, 0],
        #     [1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1, 1, 0, 1, 1],
        # ]
        # m, n = 3, 2
        # torus = Torus(values, m, n, "storage.txt")
        # torus.transpose()

        self.constr_log = []  # DBTConstructionLog()
        values = [
            [0, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0, 1, 1, 1],
            [0, 0, 1, 1, 0, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 1],
            [0, 0, 1, 1, 0, 1, 1, 1, 0, 0, 1, 1, 0, 0, 1, 0],
            [1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1, 1, 0, 1, 1],
        ]
        src_dbt = np.array(values, dtype=np.uint8) * 255
        m, n = 3, 2
        torus = Torus(values, m, n, "storage.txt")

        torus.transpose()
        r, s, m, n = torus.r, torus.s, torus.m, torus.n
        fname = self._full_fname(s, r, n, m)

        # only for this first save
        src_dbt = src_dbt.transpose()
        io.imsave(fname, src_dbt, mode="1")

        if torus.col_sums == 0:
            array_type = ArrayType.TYPE1
        else:
            array_type = ArrayType.TYPE2
        # if array_type == ArrayType.TYPE1:
        #     seed = torus.debruijn(n)
        # else:
        #     seed = torus.debruijn(n-1)
        log_entry = DBTConstructionLogEntry(fname,
                                            (r, s, m, n),
                                            array_type=array_type,
                                            transposed=False)
        print(log_entry)

        torus.make()
        self._save_entry(torus)

        torus.make()
        self._save_entry(torus)

        torus.transpose()
        torus.make()
        self._save_entry(torus, transposed=True)

        return torus

    def _generate_8192x4096_5x5_dbt(self):
        torus = self._generate_256x256_4x4_dbt()

        torus.make()
        self._save_entry(torus)

        torus.transpose()
        torus.make()
        self._save_entry(torus, transposed=True)

    def _full_fname(self, w, h, win_w, win_h):
        return f"{self._base_fname}{w}x{h}_{win_w}x{win_h}.png"

    def _save_entry(self, torus, transposed=False):
        r, s, m, n = torus.r, torus.s, torus.m, torus.n
        fname = self._full_fname(s, r, n, m)
        torus.save(fname)
        if torus.col_sums == 0:
            array_type = ArrayType.TYPE1
        else:
            array_type = ArrayType.TYPE2
        # if array_type == ArrayType.TYPE1:
        #     seed = torus.debruijn(n)
        # else:
        #     seed = torus.debruijn(n-1)
        log_entry = DBTConstructionLogEntry(fname,
                                            (r, s, m, n),
                                            array_type=array_type,
                                            transposed=transposed)
        self.constr_log.append(log_entry)


# TODO/FIXME: Maybe inherit from the list type to get append(), __iter__(),
# etc.
class DBTConstructionLog(object):

    """The DBTConstructionLog class is supposed to hold and provide the data of
    the de Bruijn torus construction / generation."""

    def __init__(self):
        """Initialize new construction log."""
        self._log = []

    def append_entry(self, log_entry):
        self._log.append(log_entry)


class DBTConstructionLogEntry(object):

    """The DBTConstructionLogEntry class is supposed to hold and provide the
    data of a single step in the de Bruijn torus construction / generation."""

    def __init__(self, fname, dbt_dim, array_type=None, seed=None,
                 transposed=False):
        """Create a new log entry for the de Bruijn torus construction.

        :fname: File name of the PNG that holds the de Bruijn torus data.
        :dbt_dim: The dimensions (r, s; m, n) of the de Bruijn torus.
        r is the height of the de Bruijn torus.
        s is the width of the de Bruijn torus.
        m is the window height of the de Bruijn torus.
        n is the window width of the de Bruijn torus.
        :array_type: The type of array (TYPE1 or TYPE2) that was used in the
        construction of the de Bruijn torus. If the type is NONE the torus used
        was not constructed (indicate brute force search).
        :seed: The de Bruijn sequence used for construction.
        :transposed: Mark if the torus was transposed.

        """
        self._fname = fname
        self._transposed = transposed
        # TODO: Reconstruct array type if not given.
        self._r, self._s, self._m, self._n = dbt_dim
        # TODO: Reconstruct array type if not given.
        self._array_type = array_type
        # TODO: Reconstruct seed if not given.
        self._seed = seed
        self._transposed = transposed


class ArrayType(Enum):
    NONE = auto()
    TYPE1 = auto()
    TYPE2 = auto()
