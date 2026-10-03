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
