import os
from torus import Torus
import numpy as np
from skimage import io
from enum import Enum, auto
from PIL import Image


class TorusGenerator(object):
    """Records and saves pertinent data of de Bruijn torus generation."""

    def __init__(self, w, h, win_w, win_h, force=False, base_fname="output-",
                 storage="storage.txt"):
        """Set dimensions of final de Bruijn torus.

        @param w: Width of final de Bruijn torus.
        @type  w: int

        @param h: Height of final de Bruijn torus.
        @type  h: int

        @param win_w: Window width of de Bruijn torus.
        @type  win_w: int

        @param win_h: Window height of de Bruijn torus.
        @type  win_h: int

        @param force: Force generation and ignore cached images.
        @type  force: bool

        @param base_fname: Base file name to save the de Bruijn tori to. Full
        name will be base_fname + "{w}x{h}_{win_w}x{win_h}.png".
        @type  base_fname: str

        @param storage: Name of a file that will be used as storage. If the
        name already exists, the file will be overwritten.
        @type  storage: str
        """
        self._s = w
        self._r = h
        self._n = win_w
        self._m = win_h
        self._base_fname = base_fname
        self._force = force
        self._storage = storage

        self.constr_log = []

        if self._r == self._s == 256 and self._m == self._n == 4:
            self._generate_256x256_4x4_dbt()
        elif self._r == 4096 and self._s == 8192 and self._m == self._n == 5:
            self._generate_8192x4096_5x5_dbt()
        else:
            err_msg = "Dimensions not possible or not supported yet."
            raise ValueError(err_msg)

    def _generate_256x256_4x4_dbt(self):
        values = [
            [0, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0, 1, 1, 1],
            [0, 0, 1, 1, 0, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 1],
            [0, 0, 1, 1, 0, 1, 1, 1, 0, 0, 1, 1, 0, 0, 1, 0],
            [1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1, 1, 0, 1, 1],
        ]
        m, n = 3, 2
        src_dbt = np.array(values, dtype=np.uint8) * 255
        torus = Torus(values, m, n, self._storage)
        gen_steps = [GenStep.TRANSPOSE,
                     GenStep.MAKE,
                     GenStep.MAKE,
                     GenStep.TRANSPOSE,
                     GenStep.MAKE,
                     GenStep.FINAL_SAVE]
        if not self._check_cache(torus, gen_steps):
            self._run_gen_steps(torus, src_dbt, gen_steps)

    def _generate_8192x4096_5x5_dbt(self):
        values = [
            [0, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0, 1, 1, 1],
            [0, 0, 1, 1, 0, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 1],
            [0, 0, 1, 1, 0, 1, 1, 1, 0, 0, 1, 1, 0, 0, 1, 0],
            [1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1, 1, 0, 1, 1],
        ]
        m, n = 3, 2
        src_dbt = np.array(values, dtype=np.uint8) * 255
        torus = Torus(values, m, n, self._storage)
        gen_steps = [GenStep.TRANSPOSE,
                     GenStep.MAKE,
                     GenStep.MAKE,
                     GenStep.TRANSPOSE,
                     GenStep.MAKE,
                     GenStep.MAKE,
                     GenStep.TRANSPOSE,
                     GenStep.MAKE,
                     GenStep.FINAL_SAVE]
        if not self._check_cache(torus, gen_steps):
            self._run_gen_steps(torus, src_dbt, gen_steps)

    def _check_cache(self, torus, gen_steps):
        r, s, m, n = torus.r, torus.s, torus.m, torus.n
        transposed = False
        for i, step in enumerate(gen_steps):
            if step == GenStep.TRANSPOSE:
                # Use cache if possible
                if not self._force:
                    # Transpose r, s, m, n values
                    r, s, m, n = s, r, n, m
                    # Setup transpose value
                    transposed = True
                # Cache not usable
                else:
                    # reset constr_log (in case entries were appended)
                    self.constr_log = []
                    return False
            elif step == GenStep.MAKE:
                # Use cache if possible
                if not self._force and self._img_is_cached(r, s, m, n):
                    # TODO/FIXME: Assumes construction with array of type 1
                    self._save_entry_no_torus(r, s, m, n,
                                              ArrayType.TYPE1,
                                              transposed)

                    # Calc r, s, m, n of new torus (for caching).
                    # TODO/FIXME: Assumes construction with array of type 1
                    r, s, m, n = r, (2**n)*s, m+1, n
                # Cache not usable
                else:
                    # reset constr_log (in case entries were appended)
                    self.constr_log = []
                    return False

                # Reset transposed
                transposed = False
            elif step == GenStep.FINAL_SAVE:
                if not self._force and self._img_is_cached(r, s, m, n):
                    # TODO/FIXME: Assumes construction with array of type 1
                    self._save_entry_no_torus(r, s, m, n,
                                              ArrayType.TYPE1,
                                              transposed)
                # Cache not usable
                else:
                    # reset constr_log (in case entries were appended)
                    self.constr_log = []
                    return False
        return True

    def _img_is_cached(self, r, s, m, n):
        return os.path.exists(self._full_fname(s, r, n, m))

    def _run_gen_steps(self, torus, src_dbt, gen_steps):
        for i, step in enumerate(gen_steps):
            if step == GenStep.TRANSPOSE:
                torus.transpose()
            elif step == GenStep.MAKE:
                # Setup transposed value
                if i > 0:
                    transposed = gen_steps[i-1] == GenStep.TRANSPOSE
                else:
                    transposed = False
                # Save log entry
                self._save_entry(torus, transposed, src_dbt)
                torus.make()
                # Unset src_dbt after the first save.
                src_dbt = None
            elif step == GenStep.FINAL_SAVE:
                # The last entry is only used for saving the image and its
                # filename for the pdf generation code.
                self._save_entry(torus)

    def _full_fname(self, w, h, win_w, win_h):
        return f"{self._base_fname}{w}x{h}_{win_w}x{win_h}.png"

    def _save_entry(self, torus, transposed=False, src_dbt=None):
        r, s, m, n = torus.r, torus.s, torus.m, torus.n
        fname = self._full_fname(s, r, n, m)

        # Save image to disk (if image cache is ignored or not cached yet)
        if self._force or not self._img_is_cached(r, s, m, n):
            if src_dbt is not None:
                if transposed:
                    src_dbt = src_dbt.transpose()
                Image.fromarray(src_dbt).convert("1").save(fname)
            else:
                torus.save(fname)
            TorusGenerator._extend_png(fname, s, r, n, m)

        # Get array_type
        if torus.col_sums == 0:
            array_type = ArrayType.TYPE1
        else:
            array_type = ArrayType.TYPE2

        # Create de Bruijn sequence seed
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

        # Create and save log entry
        log_entry = DBTConstructionLogEntry(fname,
                                            (r, s, m, n),
                                            array_type=array_type,
                                            seed=seed,
                                            transposed=transposed)
        self.constr_log.append(log_entry)

    def _save_entry_no_torus(self, r, s, m, n, array_type, transposed):
        fname = self._full_fname(s, r, n, m)
        # TODO/FIXME: Assumes construction with array of type 1
        array_type = ArrayType.TYPE1

        # Create de Bruijn sequence seed
        if array_type == ArrayType.TYPE1:
            seed = Torus.debruijn(n)
            seed = seed[1:]
            seed = seed + seed[:n-1]
            seed = np.array(seed) * 255
        else:
            # TODO/FIXME: Read paper for Type 2 and look up if this
            # is correct.
            seed = Torus.debruijn(n-1)
            seed = seed[1:]
            seed = seed + seed[:n-2]
            seed = np.array(seed) * 255

        # Create and save log entry
        log_entry = DBTConstructionLogEntry(fname,
                                            (r, s, m, n),
                                            array_type=array_type,
                                            seed=seed,
                                            transposed=transposed)
        self.constr_log.append(log_entry)

    # TODO: Maybe move extend/reduce functions to a utility script.
    def _extend_png(fname, w, h, win_w, win_h):
        array = io.imread(fname)
        array = TorusGenerator._extend_dbt(array, w, h, win_w, win_h)
        Image.fromarray(array).convert("1").save(fname)

    def _extend_dbt(array, w, h, win_w, win_h):
        # Check if parameters are valid
        if array.shape[1] != w or array.shape[0] != h:
            raise ValueError("Array and DBT dimensions do not match!")
        # Add left columns
        array = np.hstack((array, array[:, 0:win_w-1]))
        # Add top rows
        return np.vstack((array, array[0:win_h-1, ]))

    def _reduce_png(fname, w, h, win_w, win_h):
        array = io.imread(fname)
        array = TorusGenerator._reduce_dbt(array, w, h, win_w, win_h)
        Image.fromarray(array).convert("1").save(fname)

    def _reduce_dbt(array, w, h, win_w, win_h):
        # Check if parameters are valid
        if array.shape[1] != w+win_w-1 or array.shape[0] != h+win_h-1:
            raise ValueError("Array and DBT dimensions do not match!")
        # Crop to reduced size
        return array[0:h, 0:w]


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

        @param fname: File name of the PNG that holds the de Bruijn torus data.
        @type  fname: str

        @param dbt_dim: The dimensions (r, s; m, n) of the de Bruijn torus.
        r is the height of the de Bruijn torus.
        s is the width of the de Bruijn torus.
        m is the window height of the de Bruijn torus.
        n is the window width of the de Bruijn torus.
        @type  dbt_dim: tuple

        @param array_type: The type of array (TYPE1 or TYPE2) that was used in
        the construction of the de Bruijn torus. If the type is NONE the torus
        used was not constructed (indicate brute force search).
        @type  array_type: <enum 'ArrayType'>

        @param seed: The de Bruijn sequence used for construction.
        @type  seed: numpy.ndarray

        @param transposed: Mark if the torus was transposed.
        @type  transposed: bool
        """
        self.fname = fname
        # TODO: Reconstruct dimensions from fname if not given.
        self.dimensions = dbt_dim
        self.r, self.s, self.m, self.n = self.dimensions
        # TODO: Reconstruct array type if not given.
        self.array_type = array_type
        # TODO: Reconstruct seed if not given.
        self.seed = seed
        self.transposed = transposed

    def __str__(self):
        strings = [f"object: {repr(self)}"]
        strings.append(f"fname: {self.fname}")
        strings.append(f"dimensions(r,s;m,n): {self.dimensions}")
        strings.append(f"array_type: {self.array_type}")
        strings.append(f"seed: {self.seed}")
        strings.append(f"transposed: {self.transposed}")
        return ", ".join(strings)


class ArrayType(Enum):
    NONE = auto()
    TYPE1 = auto()
    TYPE2 = auto()


class GenStep(Enum):
    TRANSPOSE = auto()
    MAKE = auto()
    FINAL_SAVE = auto()
