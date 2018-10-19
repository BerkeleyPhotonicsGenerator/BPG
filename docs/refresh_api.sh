#!/usr/bin/env bash
# This script uses sphinx to autogenerate documentation for BPG
# Produces output webpage in build/html, output pdf in ./BPG_User_Manual.pdf
sphinx-apidoc --force --output-dir=source/api ../BPG
make html
echo "------------MAKING PDF---------------"
make latexpdf
cp ./build/latex/BPG.pdf ./BPG_User_Manual.pdf
