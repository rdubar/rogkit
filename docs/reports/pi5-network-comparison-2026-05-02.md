# Pi 5 Network Comparison: Powerline Ethernet vs Wi-Fi

Date: 2026-05-02

## Summary

The Pi 5 should stay on wired/powerline Ethernet as the default route. Wi-Fi on
`Qubar` is competitive and much faster for traffic sent from `neo` to the Pi,
but it is not meaningfully faster for Pi-to-neo traffic, which is the direction
that matters most for serving media.

## Devices

Pi 5:

- `eth0`: `192.168.0.156`
- `wlan0`: `192.168.0.50`

Test server:

- `neo`: `192.168.0.12`
- Command: `iperf3 -s`

## Route Preference

The Pi currently prefers wired Ethernet:

```text
default via 192.168.0.1 dev eth0  metric 100
default via 192.168.0.1 dev wlan0 metric 600
```

## Link Observations

Wired/powerline Ethernet:

```text
Speed: 100Mb/s
Duplex: Full
Link detected: yes
```

Wi-Fi on `VM8004206`:

```text
freq: 5620 MHz
width: 80 MHz
signal: -59 dBm
rx bitrate: 260.0 MBit/s
tx bitrate: 292.5 MBit/s
```

Wi-Fi on `Qubar`:

```text
freq: 5180 MHz
signal: -51 dBm
rx bitrate: 200.0 MBit/s
tx bitrate: 24.0 MBit/s
```

## Latency

Gateway ping on the original Wi-Fi comparison:

```text
eth0:  3.841 ms average, 0% packet loss
wlan0: 5.053 ms average, 0% packet loss
```

Wired had slightly better latency.

## iperf3 Results

### Original Wi-Fi: `VM8004206`

```text
Pi -> neo, single stream:
eth0   60.4 Mbit/s
wlan0  64.8 Mbit/s

neo -> Pi, single stream:
eth0   27.9 Mbit/s
wlan0  29.0 Mbit/s

Pi -> neo, 4 streams:
eth0   72.2 Mbit/s
wlan0  66.5 Mbit/s
```

Conclusion: effectively tied. Wired was still the better default because it was
more stable and had lower latency.

### New Wi-Fi: `Qubar`

```text
Pi -> neo, single stream:
eth0   64.7 Mbit/s
wlan0  64.0 Mbit/s

neo -> Pi, single stream:
eth0   27.8 Mbit/s
wlan0  74.7 Mbit/s

Pi -> neo, 4 streams:
eth0   69.7 Mbit/s
wlan0  71.8 Mbit/s
```

Conclusion: `Qubar` is much better for copying files to the Pi, but it is only
roughly tied with wired for the Pi serving data out.

## Recommendation

Keep `eth0` as the default route.

Use Wi-Fi deliberately when the workload is copying data to the Pi and that
direction matters more than stable media serving. If media playback or general
server access feels inconsistent, prefer the wired/powerline route.

## Re-test Commands

On `neo`:

```sh
iperf3 -s
```

On the Pi:

```sh
iperf3 -c 192.168.0.12 -B 192.168.0.156 -t 10
iperf3 -c 192.168.0.12 -B 192.168.0.50 -t 10
iperf3 -c 192.168.0.12 -B 192.168.0.156 -t 10 -R
iperf3 -c 192.168.0.12 -B 192.168.0.50 -t 10 -R
iperf3 -c 192.168.0.12 -B 192.168.0.156 -t 10 -P 4
iperf3 -c 192.168.0.12 -B 192.168.0.50 -t 10 -P 4
```

