#!/bin/bash
set -e

echo "🚀 Starting NATS worker..."

# Start NATS worker
python run_nats_worker.py
