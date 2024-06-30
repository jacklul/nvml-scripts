# nvml-fan-curve

Script to control GPU fans using a custom curve.  
Simple hysteresis (on the way down) is supported.

**You will need at least driver `520.56` to use this.**

## Example usage

Admin privileges are required.

```bash
python3 nvml-fan-curve.py --curve "50:30,80:100" --hysteresis 5
```

This will run a simple linear curve starting with 30% at 50C and 100% at 80C.

> [!NOTE]
> You can also use the provided systemd service file and config.

> [!IMPORTANT]
> In multi-GPU systems you have to specify either GPU index with `--index` or GPU UUID with `--uuid`.
