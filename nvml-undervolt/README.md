# nvml-undervolt

**Currently this script is very experimental, tested on Windows only!**

This is a simple script to setup an undervolt on Linux by shifting the curve up using an offset and then locking the max clock.  
Currently there is no straightforward way to achieve this as there is no voltage/curve control on Linux so this is my hacky scripted method.

> [!WARNING]
> **You're using this script at your own risk - do not blindly set untested values - test everything either in MSI Afterburner or `nvidia-smi` command first!**

## Requirements

- at least driver version `555.42`
- admin privileges
- `nvidia-ml-py` Python package - search for `python-nvidia-ml-py` in your package manager or install it with `pip install nvidia-ml-py` globally

## Example usage

See `python3 nvml-fan-curve.py --help` for available options.

```bash
python3 nvml-undervolt.py --core-offset 100 --target-clock 1800 --transition-clock 1500 --power-limit 150 --temperature-limit 70
```

> [!WARNING]
> Don't just copy paste and run above command!  
> I suggest you to look at my example [RTX 3060 example.md](RTX%203060%20example.md) to see the actual usage.

This will set clock offset to +100 when PSTATE is 0 and clock reaches >=1500 MHz then revert the changes when it falls <=1500 MHz.  
Additionally power will be limited to 120 watts and temperature limit will be set to 70C.

> [!NOTE]
> You can also use the provided systemd service file and config.

> [!IMPORTANT]
> In multi-GPU systems you have to specify either GPU index with `--index` or GPU UUID with `--uuid`.

### What each parameter does

- `--core-offset` - the offset value that shifts the whole curve upwards

- `--memory-offset` - memory overclock offset, set it only if you know that it is stable for you

- `--target-clock` - the undervolt target frequency
  - it has to be a valid frequency value (your card can run at this exact clock)

- `--transition-clock` - the frequency that switches the undervolt ON and OFF
  - the card has to be stable at this frequency with the provided offset (does not apply to `--curve` mode)
  - it has to be a valid frequency value

- `--curve` - scales offset between transition and target clock
  - this can help with stability but will also increase the time it takes for the GPU to reach target clock as the script will be manually increasing it in small steps
  - you should set `--transition-clock` to the unchanged point at the bottom of the curve

- `--curve-increment` - by how much increment (or decrement) the clock lock
  - the script will automatically set this based on `--clock-step`
  - should be set to double the value of your card's clock offset step, for most modern cards the increments are 15 or 7.5 so 30 and 15 respectively should be set
  - you can also further increase it if you want bigger jumps when script controls the clock

- `--clock-step` - use this in case script cannot detect or sets the wrong step MHz
  - the script will automatically set this to calculated value based on differences between supported clocks

- `--power-limit` - set power limit in watts

- `--temperature-limit` - set temperature limit

- `--pstates` - defauts to 0 as that's the "full power" mode when card renders 3D stuff
  - you shouldn't change it unless your card also uses pstates 1-4 when gaming

Add `-t -v` options to see list of available clocks as well as offset step in verbose output.

For better responsiveness when increasing/decreasing the clock you should either decrease `--sleep` (`0.3` - `0.5`) or increase `--curve-increment` (just make sure it is divisible by `--clock-step`).
