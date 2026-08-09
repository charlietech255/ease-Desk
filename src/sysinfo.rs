use pyo3::prelude::*;
use std::fs;
use std::path::Path;

#[pyfunction]
pub fn cpu_percent() -> PyResult<f64> {
    // This is a simplified stateless version just to demonstrate the binding.
    // For a real accurate CPU percent, you'd need to store state between calls
    // or use a crate like sysinfo.
    // For now, we'll try to calculate a generic CPU load based on getloadavg
    // (similar to the fallback in sysinfo.py).
    
    // In Rust on Linux, we can read /proc/loadavg.
    match fs::read_to_string("/proc/loadavg") {
        Ok(contents) => {
            if let Some(load_str) = contents.split_whitespace().next() {
                if let Ok(load) = load_str.parse::<f64>() {
                    let cpus = num_cpus().unwrap_or(1);
                    return Ok((load / cpus as f64 * 100.0).min(100.0).max(0.0));
                }
            }
        }
        Err(_) => {}
    }
    Ok(5.0) // Fallback
}

#[pyfunction]
pub fn num_cpus() -> PyResult<usize> {
    if let Ok(contents) = fs::read_to_string("/proc/cpuinfo") {
        let count = contents.lines().filter(|line| line.starts_with("processor")).count();
        if count > 0 {
            return Ok(count);
        }
    }
    Ok(1)
}

#[pyfunction]
pub fn memory() -> PyResult<(u64, u64)> {
    let mut total = 0;
    let mut available = 0;
    
    if let Ok(contents) = fs::read_to_string("/proc/meminfo") {
        for line in contents.lines() {
            if line.starts_with("MemTotal:") {
                if let Some(kb_str) = line.split_whitespace().nth(1) {
                    if let Ok(kb) = kb_str.parse::<u64>() {
                        total = kb * 1024;
                    }
                }
            } else if line.starts_with("MemAvailable:") {
                if let Some(kb_str) = line.split_whitespace().nth(1) {
                    if let Ok(kb) = kb_str.parse::<u64>() {
                        available = kb * 1024;
                    }
                }
            }
        }
    }
    
    let used = if total > available { total - available } else { 0 };
    Ok((used, total))
}
