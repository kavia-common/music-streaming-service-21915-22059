#!/bin/bash
cd /home/kavia/workspace/code-generation/music-streaming-service-21915-22059/MonitoringLogging
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

