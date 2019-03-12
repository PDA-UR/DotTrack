# import os  # TODO export filenames as absolute paths
from torus import Torus
import numpy as np
from skimage import io
from enum import Enum, auto
from PIL import Image


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

        self.constr_log = []  # DBTConstructionLog()

        if self._r == self._s == 256 and self._m == self._n == 4:
            torus = self._generate_256x256_4x4_dbt()
            # The last entry is only used for saving the image and its filename for
            # the pdf generation code.
            self._save_entry(torus)
        elif self._r == 4096 and self._s == 8192 and self._m == self._n == 5:
            torus = self._generate_8192x4096_5x5_dbt()
            # The last entry is only used for saving the image and its filename for
            # the pdf generation code.
            self._save_entry(torus)
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

        # values = [
        #     [0, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0, 1, 1, 1],
        #     [0, 0, 1, 1, 0, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 1],
        #     [0, 0, 1, 1, 0, 1, 1, 1, 0, 0, 1, 1, 0, 0, 1, 0],
        #     [1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1, 1, 0, 1, 1],
        # ]
        # src_dbt = np.array(values, dtype=np.uint8) * 255
        # m, n = 3, 2
        # torus = Torus(values, m, n, "storage.txt")

        # torus.transpose()
        # r, s, m, n = torus.r, torus.s, torus.m, torus.n
        # fname = self._full_fname(s, r, n, m)
        # torus.save(fname)

        # # only for this first save
        # # src_dbt = src_dbt.transpose()
        # # io.imsave(fname, src_dbt, mode="1")

        # if torus.col_sums == 0:
        #     array_type = ArrayType.TYPE1
        # else:
        #     array_type = ArrayType.TYPE2
        # if array_type == ArrayType.TYPE1:
        #     seed = Torus.debruijn(n)
        #     seed = seed[1:]
        #     seed = seed + seed[:n-1]
        #     seed = np.array(seed) * 255
        # else:
        #     # TODO/FIXME: Read paper for Type 2 and look up if this is correct.
        #     seed = Torus.debruijn(n-1)
        #     seed = seed[1:]
        #     seed = seed + seed[:n-2]
        #     seed = np.array(seed) * 255
        # log_entry = DBTConstructionLogEntry(fname,
        #                                     (r, s, m, n),
        #                                     array_type=array_type,
        #                                     seed=seed,
        #                                     transposed=True)
        # torus.make()

        values = [
            [0, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0, 1, 1, 1],
            [0, 0, 1, 1, 0, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 1],
            [0, 0, 1, 1, 0, 1, 1, 1, 0, 0, 1, 1, 0, 0, 1, 0],
            [1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1, 1, 0, 1, 1],
        ]
        m, n = 3, 2
        src_dbt = np.array(values, dtype=np.uint8) * 255
        torus = Torus(values, m, n, "storage.txt")

        torus.transpose()
        self._save_entry(torus, transposed=True, src_dbt=src_dbt)
        torus.make()

        self._save_entry(torus)
        torus.make()

        torus.transpose()
        self._save_entry(torus, transposed=True)
        torus.make()

        return torus

    def _generate_8192x4096_5x5_dbt(self):
        torus = self._generate_256x256_4x4_dbt()

        self._save_entry(torus)
        torus.make()

        torus.transpose()
        self._save_entry(torus, transposed=True)
        torus.make()

        return torus

    def _full_fname(self, w, h, win_w, win_h):
        return f"{self._base_fname}{w}x{h}_{win_w}x{win_h}.png"

    def _save_entry(self, torus, transposed=False, src_dbt=None):
        r, s, m, n = torus.r, torus.s, torus.m, torus.n
        fname = self._full_fname(s, r, n, m)
        if src_dbt is not None:
            if transposed:
                src_dbt = src_dbt.transpose()
            Image.fromarray(src_dbt).convert("1").save(fname)
        else:
            torus.save(fname)
        self._extend_png(fname, n, m)
        if torus.col_sums == 0:
            array_type = ArrayType.TYPE1
        else:
            array_type = ArrayType.TYPE2
        if array_type == ArrayType.TYPE1:
            seed = Torus.debruijn(n)
            seed = seed[1:]
            seed = seed + seed[:n-1]
            seed = np.array(seed) * 255
        else:
            # TODO/FIXME: Read paper for Type 2 and look up if this is correct.
            seed = Torus.debruijn(n-1)
            seed = seed[1:]
            seed = seed + seed[:n-2]
            seed = np.array(seed) * 255
        log_entry = DBTConstructionLogEntry(fname,
                                            (r, s, m, n),
                                            array_type=array_type,
                                            seed=seed,
                                            transposed=transposed)
        self.constr_log.append(log_entry)

    def _extend_png(self, fname, win_w, win_h):
        array = io.imread(fname)
        top_rows = array[0:win_h-1, ]
        left_cols = array[:, 0:win_w-1]
        top_left_corner = array[0:win_h-1, 0:win_w-1]
        bottom = np.hstack((top_rows, top_left_corner))
        left_added = np.hstack((array, left_cols))
        bottom_added = np.vstack((left_added, bottom))
        new_array = bottom_added
        # print(new_array)
        Image.fromarray(new_array).convert("1").save(fname)


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
        self.fname = fname
        # TODO: Reconstruct array type if not given.
        self.dimensions = dbt_dim
        self.r, self.s, self.m, self.n = self.dimensions
        # TODO: Reconstruct array type if not given.
        self.array_type = array_type
        # TODO: Reconstruct seed if not given.
        self.seed = seed
        self.transposed = transposed

    # def __repr__(self):
    #     strings = [f"{str(self.fname)}"]
    #     strings.append(f"{str(self.dimensions)}")
    #     strings.append(f"{str(self.array_type)}")
    #     strings.append(f"{str(self.seed)}")
    #     strings.append(f"{str(self.transposed)}")
    #     return "".join(strings)

    def __str__(self):
        strings = [f"object: {repr(self)}"]
        strings.append(f"fname: {self.fname}")
        strings.append(f"dimensions(r,s;m,n): {self.dimensions}")
        strings.append(f"array_type: {self.array_type}")
        strings.append(f"seed: {self.seed}")
        strings.append(f"transposed: {self.transposed}")
        return ", ".join(strings)
        # return unicode(self).encode("utf-8")

    # def __unicode__(self):
    #     strings = [f"{str(self.fname)}"]
    #     strings.append(f"{str(self.dimensions)}")
    #     strings.append(f"{str(self.array_type)}")
    #     strings.append(f"{str(self.seed)}")
    #     strings.append(f"{str(self.transposed)}")
    #     return "".join(strings)


class ArrayType(Enum):
    NONE = auto()
    TYPE1 = auto()
    TYPE2 = auto()
