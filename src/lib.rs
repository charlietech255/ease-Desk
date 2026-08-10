use pyo3::prelude::*;

mod sysinfo;

/// `ease_desk_core`
/// High-performance Rust native extension for ease-Desk.
/// This module exposes fast system bindings (like real-time CPU/RAM stats) 
/// to the Python shell via PyO3, bypassing slow subprocess calls.
#[pymodule]
fn ease_desk_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sysinfo::cpu_percent, m)?)?;
    m.add_function(wrap_pyfunction!(sysinfo::memory, m)?)?;
    m.add_function(wrap_pyfunction!(sysinfo::num_cpus, m)?)?;
    Ok(())
}
