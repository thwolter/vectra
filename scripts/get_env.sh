#!/bin/bash

echo "Setting up environment variables..."
op inject -i ./scripts/.env.tpl -o .env
