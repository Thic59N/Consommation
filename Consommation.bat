@echo off
title Lancement Consommation Voitures
cd /d "%~dp0"
echo Verification des installations...
streamlit run Consommation.py
pause