# Example based on my RTX 3060

## Using curve-up method (example, not stable on my card)

- my undervolt point is 1957 MHz @ 950 mV, that is +160 offset
- when entering PSTATE 0 my card's initial clock is 1807 MHz

```bash
python3 nvml-undervolt.py --core-offset 160 --target-clock 1957 --transition-clock 1807
```

## Using simple one-point undervolt method

- my top curve point is 1957 MHz @ 950 mV, that is +160 offset
- my bottom curve point is at 1747 MHz
- my card uses 7.5 MHz clock offset steps

```bash
python3 nvml-undervolt.py --core-offset 160 --target-clock 1957 --transition-clock 1747 --curve --curve-increment 15
```

## Results for the second method

### My card's stock settings

The clock goes down very quickly when the temperatures go closer to 80C.

![](https://i.imgur.com/O7dRzxw.jpeg)
![](https://i.imgur.com/wzJATpM.jpeg)

### My MSI Afterburner "lazy" undervolt curve

I have never reached 80C with this setup, score in Superposition is better than on stock.

Shifting whole curve upwards doesn't work for me, it freezes at around +120 offset when at idle frequencies, so I'm sticking with this basic method.  
I might give a try the CTRL+drag method but currently have no time for proper stability testing.

![](https://i.imgur.com/ftByJir.jpeg)
![](https://i.imgur.com/NhBKA3r.jpeg)

### Frequency and voltage on "target clock" using the script

Close enough, right? This could be further tweaked by increasing the offset.

![](https://i.imgur.com/sNn1eCC.jpeg)
![](https://i.imgur.com/iVWJhdj.jpeg)

