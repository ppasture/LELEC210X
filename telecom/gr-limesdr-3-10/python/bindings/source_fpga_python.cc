/*
 * Copyright 2025 Free Software Foundation, Inc.
 *
 * This file is part of GNU Radio
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 */

/***********************************************************************************/
/* This file is automatically generated using bindtool and can be manually
 * edited  */
/* The following lines can be configured to regenerate this file during cmake */
/* If manual edits are made, the following tags should be modified accordingly.
 */
/* BINDTOOL_GEN_AUTOMATIC(0) */
/* BINDTOOL_USE_PYGCCXML(0) */
/* BINDTOOL_HEADER_FILE(source_fpga.h)                                        */
/* BINDTOOL_HEADER_FILE_HASH(d4c33ddd07c37d83f006e5113b417276) */
/***********************************************************************************/

#include <pybind11/complex.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

#include <limesdr_fpga/source_fpga.h>
// pydoc.h is automatically generated in the build directory
#include <source_fpga_pydoc.h>

void bind_source_fpga(py::module &m) {

  using source_fpga = ::gr::limesdr_fpga::source_fpga;

  py::class_<source_fpga, gr::sync_block, gr::block, gr::basic_block,
             std::shared_ptr<source_fpga>>(m, "source_fpga", D(source_fpga))

      .def(py::init(&source_fpga::make), py::arg("serial"),
           py::arg("channel_mode"), py::arg("filename"),
           py::arg("align_ch_phase"), D(source_fpga, make))

      .def("set_center_freq", &source_fpga::set_center_freq, py::arg("freq"),
           py::arg("chan") = 0, D(source_fpga, set_center_freq))

      .def("set_antenna", &source_fpga::set_antenna, py::arg("antenna"),
           py::arg("channel") = 0, D(source_fpga, set_antenna))

      .def("set_nco", &source_fpga::set_nco, py::arg("nco_freq"),
           py::arg("channel"), D(source_fpga, set_nco))

      .def("set_bandwidth", &source_fpga::set_bandwidth,
           py::arg("analog_bandw"), py::arg("channel") = 0,
           D(source_fpga, set_bandwidth))

      .def("set_digital_filter", &source_fpga::set_digital_filter,
           py::arg("digital_bandw"), py::arg("channel"),
           D(source_fpga, set_digital_filter))

      .def("set_gain", &source_fpga::set_gain, py::arg("gain_dB"),
           py::arg("channel") = 0, D(source_fpga, set_gain))

      .def("set_sample_rate", &source_fpga::set_sample_rate, py::arg("rate"),
           D(source_fpga, set_sample_rate))

      .def("set_oversampling", &source_fpga::set_oversampling,
           py::arg("oversample"), D(source_fpga, set_oversampling))

      .def("calibrate", &source_fpga::calibrate, py::arg("bandw"),
           py::arg("channel") = 0, D(source_fpga, calibrate))

      .def("set_buffer_size", &source_fpga::set_buffer_size, py::arg("size"),
           D(source_fpga, set_buffer_size))

      .def("set_tcxo_dac", &source_fpga::set_tcxo_dac, py::arg("dacVal") = 125,
           D(source_fpga, set_tcxo_dac))

      .def("write_lms_reg", &source_fpga::write_lms_reg, py::arg("address"),
           py::arg("val"), D(source_fpga, write_lms_reg))

      .def("set_dspcfg_preamble", &source_fpga::set_dspcfg_preamble,
           py::arg("dspcfg_PASSTHROUGH_LEN") = 100U,
           py::arg("dspcfg_THRESHOLD") = 100U,
           py::arg("dspcfg_preamble_en") = 0,
           D(source_fpga, set_dspcfg_preamble))

      .def("get_dspcfg_long_sum", &source_fpga::get_dspcfg_long_sum,
           D(source_fpga, get_dspcfg_long_sum))

      .def("get_dspcfg_short_sum", &source_fpga::get_dspcfg_short_sum,
           D(source_fpga, get_dspcfg_short_sum))

      .def("set_gpio_dir", &source_fpga::set_gpio_dir, py::arg("dir"),
           D(source_fpga, set_gpio_dir))

      .def("write_gpio", &source_fpga::write_gpio, py::arg("out"),
           D(source_fpga, write_gpio))

      .def("read_gpio", &source_fpga::read_gpio, D(source_fpga, read_gpio))

      ;
}
