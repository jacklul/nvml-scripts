# nvml-fan-curve

Script to control GPU fans using a custom curve.  
Simple hysteresis (on the way down) is supported.

## Requirements

- at least driver version `520.56`
- admin privileges
- `nvidia-ml-py` Python package - search for `python-nvidia-ml-py` in your package manager or install it with `pipx --global install nvidia-ml-py`

## Example usage

See `python3 nvml-fan-curve.py --help` for available options.

```bash
python3 nvml-fan-curve.py --curve "50:30,60:65,80:100" --hysteresis 5
```

This will run a simple linear curve starting with 30% at 50C and 100% at 80C.  

> [!NOTE]
> You can also use the provided systemd service file and config.

> [!IMPORTANT]
> In multi-GPU systems you have to specify either GPU index with `--index` or GPU UUID with `--uuid`.
