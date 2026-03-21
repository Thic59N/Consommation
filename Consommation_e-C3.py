import subprocess, sys, os

# --- AUTO-INSTALLATION ---
def install_requirements():
    if os.environ.get("STREAM_LIMIT_RUNTIME_EXECUTION_MODE") is None:
        packages = ["streamlit", "gspread", "google-auth", "pandas"]
        for p in packages:
            try:
                __import__(p)
            except ImportError:
                subprocess.check_call([sys.executable, "-m", "pip", "install", p])

install_requirements()

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

# --- FONCTIONS DE CALCUL ---
def extraire_nombre(valeur):
    if not valeur: return 0.0
    nettoye = "".join(c for c in str(valeur) if c.isdigit() or c in ".,-")
    nettoye = nettoye.replace(',', '.')
    try: return float(nettoye)
    except: return 0.0

def temps_vers_minutes(t):
    if not t or ":" not in t: return 0
    try:
        h, m = map(int, t.split(':'))
        return h * 60 + m
    except: return 0

def minutes_vers_temps(total_min):
    h = total_min // 60
    m = total_min % 60
    return f"{h}:{m:02d}"

# --- CONNEXION ---
def connecter_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    path_json = os.path.join(os.path.dirname(__file__), "credentials.json")
    try:
        if os.path.exists(path_json):
            creds = Credentials.from_service_account_file(path_json, scopes=scope)
        else:
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key("1O2bv779GffFziT9TKcfLgRtYLahKsJ7liNncQM7j-gg")
    except Exception as e:
        st.error(f"Erreur connexion : {e}")
        return None

# --- CONFIG PAGE ---
st.set_page_config(page_title="Consommation Voitures", layout="wide")
tab_saisie, tab_visualisation = st.tabs(["📝 Nouvelle Recharge", "📊 Historique Sheets"])

with tab_saisie:
    st.header("⚡ Gestion des Recharges")
    annee = st.radio("Année :", ["2025", "2026"], horizontal=True, index=1)
    
    doc = connecter_sheet()
    charge_en_cours = False
    num_ligne_active = None
    toutes_valeurs = []

    if doc:
        sheet = doc.worksheet(f"Recharge {annee}")
        toutes_valeurs = sheet.get_all_values()
        if len(toutes_valeurs) >= 4:
            derniere_ligne = toutes_valeurs[-1]
            num_ligne_active = len(toutes_valeurs)
            if len(derniere_ligne) > 1 and derniere_ligne[1] != "" and (len(derniere_ligne) <= 3 or (len(derniere_ligne) > 3 and (derniere_ligne[3] == "" or derniere_ligne[3] is None))):
                charge_en_cours = True
                donnees_derniere_ligne = derniere_ligne

    if charge_en_cours:
        st.subheader("🏁 Terminer la charge")
        st.info(f"🔋 Débutée le {donnees_derniere_ligne[0]} à {donnees_derniere_ligne[1]} km")

        date_fin = st.date_input("Date de fin de charge", datetime.now(), format="DD/MM/YYYY")
        # % Batterie Final Obligatoire
        p_fin_saisi = st.number_input("% Batterie final *", 0, 100, value=None, placeholder="Obligatoire")

        st.divider()

        # --- CALCULATRICES OCTOPUS ---
        st.markdown("### 🧮 Calculatrices Octopus")
        col_t, col_e = st.columns(2)
        
        with col_t:
            st.markdown("**⏱️ Sessions de Temps (H:MM)**")
            # Sess 1 Obligatoire
            t1 = st.text_input("Sess. 1 *", value="", placeholder="Obligatoire (ex: 2:38)", key="calc_t1")
            t2 = st.text_input("Sess. 2", value="", placeholder="Optionnel", key="calc_t2")
            t3 = st.text_input("Sess. 3", value="", placeholder="Optionnel", key="calc_t3")
            t4 = st.text_input("Sess. 4", value="", placeholder="Optionnel", key="calc_t4")
            
            if st.button("🔄 Valider le Temps Total"):
                if not t1 or ":" not in t1:
                    st.error("La Session 1 est obligatoire au format H:MM")
                else:
                    total_min = sum([temps_vers_minutes(t) for t in [t1, t2, t3, t4]])
                    st.session_state['temps_final'] = minutes_vers_temps(total_min)

            if 'temps_final' in st.session_state:
                st.success(f"Temps retenu : **{st.session_state['temps_final']}**")

        with col_e:
            st.markdown("**🔌 Sessions d'Énergie (kWh)**")
            # kWh 1 Obligatoire
            en1 = st.number_input("kWh 1 *", min_value=0.0, step=0.01, format="%.2f", value=None, placeholder="Obligatoire", key="calc_e1")
            en2 = st.number_input("kWh 2", min_value=0.0, step=0.01, format="%.2f", value=None, placeholder="Optionnel", key="calc_e2")
            en3 = st.number_input("kWh 3", min_value=0.0, step=0.01, format="%.2f", value=None, placeholder="Optionnel", key="calc_e3")
            en4 = st.number_input("kWh 4", min_value=0.0, step=0.01, format="%.2f", value=None, placeholder="Optionnel", key="calc_e4")
            
            if st.button("🔄 Valider l'Énergie Totale"):
                if en1 is None or en1 == 0.0:
                    st.error("Le kWh 1 est obligatoire")
                else:
                    tot_e = sum([en if en is not None else 0.0 for en in [en1, en2, en3, en4]])
                    st.session_state['energie_finale'] = round(tot_e, 2)

            if 'energie_finale' in st.session_state:
                st.success(f"Énergie retenue : **{st.session_state['energie_finale']} kWh**")

        st.divider()

        # --- VALIDATION FINALE ---
        t_final = st.session_state.get('temps_final', "0:00")
        e_final = st.session_state.get('energie_finale', 0.0)
        
        with st.form("formulaire_final_save"):
            st.write(f"📊 **Résumé :** Batterie {p_fin_saisi}% | Temps {t_final} | Énergie {e_final} kWh")
            
            with st.expander("📍 Lieu et Prix (Optionnel)"):
                lieu_selection = st.selectbox("Lieu", ["Maison", "Borne Publique", "Ionity", "Tesla Supercharger", "Autre..."])
                lieu_precis = st.text_input("Si Autre, précisez")
                prix_kwh = st.number_input("Coût €/kWh", value=0.1579, format="%.4f")

            if st.form_submit_button("✅ TOUT ENREGISTRER DANS SHEETS"):
                # Vérification ultime des 3 piliers obligatoires
                if p_fin_saisi is None:
                    st.error("⚠️ Le % de Batterie final est obligatoire.")
                elif not t1 or ":" not in t1 or 'temps_final' not in st.session_state:
                    st.error("⚠️ La Session 1 de temps est obligatoire (et doit être validée).")
                elif en1 is None or en1 == 0.0 or 'energie_finale' not in st.session_state:
                    st.error("⚠️ Le kWh 1 est obligatoire (et doit être validé).")
                else:
                    lieu_final = lieu_precis if (lieu_selection == "Autre..." and lieu_precis) else lieu_selection
                    sheet.update_cell(num_ligne_active, 1, date_fin.strftime("%d/%m/%Y"))
                    sheet.update_cell(num_ligne_active, 4, p_fin_saisi / 100)
                    sheet.update_cell(num_ligne_active, 5, t_final)
                    sheet.update_cell(num_ligne_active, 6, e_final)
                    sheet.update_cell(num_ligne_active, 10, prix_kwh)
                    sheet.update_cell(num_ligne_active, 12, lieu_final)
                    
                    for key in ['temps_final', 'energie_finale']:
                        if key in st.session_state: del st.session_state[key]
                    
                    st.success("Données enregistrées !")
                    st.balloons()
                    st.rerun()

    else:
        # Bloc création nouvelle charge (KM et Batt départ obligatoires)
        st.subheader("🚀 Lancer une nouvelle charge")
        km_precedent = 0
        km_suggere = 0
        if len(toutes_valeurs) > 3:
            km_precedent = extraire_nombre(toutes_valeurs[-1][1])
            km_suggere = int(km_precedent // 100) * 100

        with st.form("form_debut"):
            date_j = st.date_input("Date de début", datetime.now(), format="DD/MM/YYYY")
            km_actuel = st.number_input("Kilométrage au compteur", value=int(km_suggere))
            p_dep = st.number_input("% Batterie au départ *", 0, 100, value=None, placeholder="Obligatoire")
            
            if st.form_submit_button("🚀 Créer la ligne"):
                if p_dep is not None and km_actuel > km_precedent:
                    sheet.append_row([date_j.strftime("%d/%m/%Y"), km_actuel, "", p_dep/100], value_input_option="USER_ENTERED")
                    st.rerun()
                else:
                    st.error("Vérifiez km (> précédent) et batterie.")