# Example based on my RTX 3060

## Using curve-up method (example, not stable on my card)

- my undervolt point is 1957 MHz @ 950 mV, that is +158 offset (157.5)
- when entering PSTATE 0 my card's initial clock is 1807 MHz

```bash
python3 nvml-undervolt.py --core-offset 158 --target-clock 1957 --transition-clock 1807
```

## Using simple one-point undervolt method

- my top curve point is 1957 MHz @ 950 mV, that is +158 offset (157.5)
- my bottom curve point is at 1740 MHz (0 offset)
- my card uses 7.5 MHz clock offset steps

```bash
python3 nvml-undervolt.py --core-offset 158 --target-clock 1957 --transition-clock 1740 --curve --curve-increment 15
```

_`--curve-increment` should be automatically set and in most cases you don't have to provide that option._

## Results for the second method

### My card's stock settings

The clock goes down very quickly when the temperatures go closer to 80C.

![](https://i.imgur.com/O7dRzxw.jpeg)
![](https://i.imgur.com/ErJE7YV.jpeg)

### My MSI Afterburner "lazy" undervolt curve

I have never reached 80C with this setup, score in Superposition is better than on stock.

Shifting whole curve upwards doesn't work for me, it freezes at around +120 offset when at idle frequencies, so I'm sticking with this basic method.  
I might give a try the CTRL+drag method but currently have no time for proper stability testing.

![](https://i.imgur.com/ftByJir.jpeg)
![](https://i.imgur.com/7sR1Z2f.jpeg)

### Frequency and voltage on "target clock" using the script

Close enough, right? This could be further tweaked by increasing the offset.  
Unfortunately because we are using a trickery here sometimes the voltage will be higher than what we wanted, other times it can be a bit lower - it is important to account for that and have some stability buffer.

![](https://i.imgur.com/sNn1eCC.jpeg)
![](https://i.imgur.com/2u0GfCy.jpeg)
