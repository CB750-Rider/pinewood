#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <math.h>

double _get_official_time(long count, double rate){
  double ot;
  ot = (double)count/rate;
  /* Round ot */
  ot = round(1000.0*ot);

  return (ot/1000.0);

}

static PyObject * get_official_time(PyObject *self, PyObject *args){
  double rate, out;
  long count;

  if (!PyArg_ParseTuple(args, "ld", &count, &rate))
    return NULL;

  out = _get_official_time(count, rate);

  return PyFloat_FromDouble(out);

}

static PyMethodDef PinewoodMethods[] = {
  {"get_official_time", get_official_time, METH_VARARGS, 
    "Convert counts to official time."},
  {NULL, NULL, 0, NULL}
};

static PyModuleDef pinewood_utils = {
  PyModuleDef_HEAD_INIT,
  "pinewood",
  NULL,
  -1,
  PinewoodMethods
};

PyMODINIT_FUNC PyInit_pinewood_utils(void){
  return PyModule_Create(&pinewood_utils);
}
