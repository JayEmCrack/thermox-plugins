# PR #1 follow-up steps (ThermoX firmware)

Run these from a local clone, on the PR #1 branch. Nothing here changes any GPIO assignment, and GPIO35 battery sense stays as-is (disabled by default) for a later decision.

```bash
git fetch origin
git checkout claude/magical-gauss-sl1l1s

# 1. Add CI that compiles the sketch
mkdir -p .github/workflows
cat > .github/workflows/compile.yml <<'EOF'
name: Compile ThermoX
on:
  pull_request:
  push:
    branches: [main]
jobs:
  compile:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: arduino/setup-arduino-cli@v2
      - name: Install ESP32 core and libraries
        run: |
          arduino-cli config init
          arduino-cli config add board_manager.additional_urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
          arduino-cli core update-index
          arduino-cli core install esp32:esp32
          # Add the libraries ThermoX.ino includes (check its #include lines), for example:
          # arduino-cli lib install "U8g2" "OneWire" "DallasTemperature"
      - name: Compile
        run: arduino-cli compile --fqbn esp32:esp32:esp32 ThermoX
EOF

# 2. Remove the duplicate zip (the dashboard sources are already in the repo)
git rm thermox-dashboard.zip

git add .github/workflows/compile.yml
git commit -m "Add compile CI and remove duplicate dashboard zip"
git push origin claude/magical-gauss-sl1l1s
```

Then mark PR #1 "Ready for review" on GitHub (button at the bottom of the PR page).

## Optional safety suggestion
Enable the ESP32 task watchdog in `setup()` and feed it in `loop()`, so a hung control loop cannot leave the Peltier driven.

## One run per press, full power (patch)
`patches/one-shot-full-power.patch` changes the firmware (`ThermoX/ThermoX.ino` and `ThermoX/README.md`) so that:
- a button press starts one run toward the target at full Peltier power (no taper, no hysteresis band);
- at the target the Peltier and fan switch off and stay off, even if the temperature drifts, until the next press;
- nothing starts at power-up (OLED shows READY, then REACHED after a run);
- the 60 s hot/cold reversal rest and all fault cutoffs are unchanged, and the log `MODE=` values are unchanged
  (still `HEATING`, `COOLING`, `IDLE`, `FAULT`), so `dashboard/api/log.php` keeps accepting every line.

Apply it on the PR #1 branch, after the steps above:

```bash
git apply --check patches/one-shot-full-power.patch && git apply patches/one-shot-full-power.patch
git add ThermoX && git commit -m "One run per button press at full power"
git push origin claude/magical-gauss-sl1l1s
```

Checked on a computer by compiling the changed sketch against stub Arduino headers (no new warnings) and running its real `control()` code
against a mock board and a simple water model: no start at power-up, full duty on one side only, stop at target, no restart after
a +5 °C or -4 °C drift, reversal rest then heat, direction change mid-run, press before the first sensor reading, and the sensor,
fan-stall and over-temperature faults. It has not been compiled for the ESP32 or run on hardware.

## Ready-made files (no git needed)
`updated-firmware/ThermoX/ThermoX.ino` and `updated-firmware/ThermoX/README.md` are the full PR #1 files with the patch above already applied.
Open `updated-firmware/ThermoX/ThermoX.ino` in the Arduino IDE to flash it, or copy both files over `ThermoX/ThermoX.ino` and
`ThermoX/README.md` on the PR #1 branch. The folder is named `ThermoX` so the Arduino IDE accepts it. Delete `updated-firmware/` once PR #1 contains these changes.
