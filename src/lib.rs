use pyo3::prelude::*;

mod sysinfo;

/// A Python module implemented in Rust.
#[pymodule]
fn ease_desk_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sysinfo::cpu_percent, m)?)?;
    m.add_function(wrap_pyfunction!(sysinfo::memory, m)?)?;
    m.add_function(wrap_pyfunction!(sysinfo::num_cpus, m)?)?;
    Ok(())
}
