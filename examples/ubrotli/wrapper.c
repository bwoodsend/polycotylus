#define PY_SSIZE_T_CLEAN
#include "brotli/decode.h"
#include "brotli/encode.h"
#include <Python.h>

static PyObject *compress(PyObject *dummy, PyObject *args, PyObject *kwargs) {
  uint8_t *buffer;
  Py_ssize_t length;
  int mode = BROTLI_DEFAULT_MODE;
  int window = BROTLI_DEFAULT_WINDOW;
  int quality = BROTLI_DEFAULT_QUALITY;
  static char *keywords[] = {"buffer", "mode", "window", "quality", NULL};

  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "y#|iii", keywords, &buffer,
                                   &length, &mode, &window, &quality))
    return NULL;

  size_t compressed_length;
  uint8_t *output;
  size_t output_size = length;
  while (1) {
    output = PyMem_Malloc(output_size);
    compressed_length = output_size;
    BROTLI_BOOL ok = BrotliEncoderCompress(quality, window, mode, length,
                                           buffer, &compressed_length, output);
    if (ok)
      break;
    else {
      PyMem_Free(output);
      output_size *= 2;
    }
  }
  return PyBytes_FromStringAndSize((char *)output, compressed_length);
}

static PyObject *decompress(PyObject *dummy, PyObject *args) {
  uint8_t *buffer;
  Py_ssize_t length;

  if (!PyArg_ParseTuple(args, "y#", &buffer, &length))
    return NULL;

  size_t decompressed_length;
  uint8_t *output;
  size_t output_size = length * 4;

  while (1) {
    output = PyMem_Malloc(output_size);
    decompressed_length = output_size;
    BrotliDecoderResult status =
        BrotliDecoderDecompress(length, buffer, &decompressed_length, output);
    if (status == BROTLI_DECODER_SUCCESS)
      break;
    else {
      if (decompressed_length) {
        PyMem_Free(output);
        output_size *= 4;
      } else {
        PyErr_SetString(PyExc_ValueError, "Invalid brotli-compressed buffer");
        return NULL;
      }
    }
  }
  return PyBytes_FromStringAndSize((char *)output, decompressed_length);
}

static PyMethodDef methods[] = {
    {"compress", (PyCFunction)compress, METH_VARARGS | METH_KEYWORDS,
     "Brotli compress a bytes-like object"},
    {"decompress", decompress, METH_VARARGS,
     "Decompress a brotli compressed buffer"},
    {NULL, NULL, 0, NULL} /* Sentinel */
};

static PyModuleDef this_module = {
    PyModuleDef_HEAD_INIT,
    .m_name = "ubrotli",
    .m_size = -1,
    .m_methods = methods,
};

PyMODINIT_FUNC PyInit_ubrotli(void) {
  PyObject *m;

  m = PyModule_Create(&this_module);
  if (m == NULL)
    return NULL;

  PyModule_AddIntConstant(m, "DEFAULT_QUALITY", BROTLI_DEFAULT_QUALITY);
  PyModule_AddIntConstant(m, "MAX_QUALITY", BROTLI_MAX_QUALITY);
  PyModule_AddIntConstant(m, "MIN_QUALITY", BROTLI_MIN_QUALITY);
  PyModule_AddIntConstant(m, "DEFAULT_WINDOW", BROTLI_DEFAULT_WINDOW);
  PyModule_AddIntConstant(m, "DEFAULT_MODE", BROTLI_DEFAULT_MODE);
  PyModule_AddIntConstant(m, "MODE_FONT", BROTLI_MODE_FONT);
  PyModule_AddIntConstant(m, "MODE_TEXT", BROTLI_MODE_TEXT);

  return m;
}
