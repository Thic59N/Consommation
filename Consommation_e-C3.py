import subprocess, sys, os

# --- AUTO-INSTALLATION ---
def install_requirements():
    if os.environ.get("STREAMLIT_RUNTIME_EXECUTION_MODE") is None:
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

        # --- 1. SAISIE VERTICALE (Date puis Batterie) ---
        date_fin = st.date_input("Date de fin de charge", datetime.now(), format="DD/MM/YYYY")
        p_fin_saisi = st.number_input("% Batterie final", 0, 100, value=None, placeholder="Ex: 80")

        st.divider()

        # --- 2. CALCULATRICES OCTOPUS ---
        st.markdown("### 🧮 Calculatrices Octopus")
        col_t, col_e = st.columns(2)
        
        with col_t:
            st.markdown("**⏱️ Sessions de Temps (H:MM)**")
            t1 = st.text_input("Sess. 1", "0:00", key="calc_t1")
            t2 = st.text_input("Sess. 2", "0:00", key="calc_t2")
            t3 = st.text_input("Sess. 3", "0:00", key="calc_t3")
            t4 = st.text_input("Sess. 4", "0:00", key="calc_t4")
            
            total_min = sum([temps_vers_minutes(t) for t in [t1, t2, t3, t4]])
            temps_calcule = minutes_vers_temps(total_min)
            if st.button("🔄 Valider le Temps Total"):
                st.session_state['temps_final'] = temps_calcule
                st.success(f"Temps retenu : {temps_calcule}")

        with col_e:
            st.markdown("**🔌 Sessions d'Énergie (kWh)**")
            en1 = st.number_input("kWh 1", 0.0, step=0.01, format="%.2f", key="calc_e1")
            en2 = st.number_input("kWh 2", 0.0, step=0.01, format="%.2f", key="calc_e2")
            en3 = st.number_input("kWh 3", 0.0, step=0.01, format="%.2f", key="calc_e3")
            en4 = st.number_input("kWh 4", 0.0, step=0.01, format="%.2f", key="calc_e4")
            
            energie_totale = round(en1 + en2 + en3 + en4, 2)
            if st.button("🔄 Valider l'Énergie Totale"):
                st.session_state['energie_finale'] = energie_totale
                st.success(f"Énergie retenue : {energie_totale} kWh")

        st.divider()

        # --- 3. VALIDATION FINALE ---
        t_final = st.session_state.get('temps_final', "0:00")
        e_final = st.session_state.get('energie_finale', 0.0)
        
        with st.form("formulaire_final_save"):
            st.write(f"📊 **Résumé :** Fin le {date_fin.strftime('%d/%m/%Y')} | Batterie {p_fin_saisi}% | {t_final} | {e_final} kWh")
            
            with st.expander("📍 Lieu et Prix (Optionnel)"):
                lieu_selection = st.selectbox("Lieu", ["Maison", "Borne Publique", "Ionity", "Tesla Supercharger", "Autre..."])
                lieu_precis = st.text_input("Si Autre, précisez")
                prix_kwh = st.number_input("Coût €/kWh", value=0.1579, format="%.4f")

            if st.form_submit_button("✅ TOUT ENREGISTRER DANS SHEETS"):
                if p_fin_saisi is None:
                    st.error("⚠️ Le % de Batterie final est obligatoire.")
                elif t_final == "0:00" or e_final == 0.0:
                    st.error("⚠️ Utilisez les boutons 'Valider' des calculatrices pour confirmer les totaux.")
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
        st.subheader("🚀 Lancer une nouvelle charge")
        km_precedent = 0
        km_suggere = 0
        if len(toutes_valeurs) > 3:
            km_precedent = extraire_nombre(toutes_valeurs[-1][1])
            km_suggere = int(km_precedent // 100) * 100

        with st.form("form_debut"):
            date_j = st.date_input("Date de début", datetime.now(), format="DD/MM/YYYY")
            km_actuel = st.number_input("Kilométrage au compteur", value=int(km_suggere))
            p_dep = st.number_input("% Batterie au départ", 0, 100, value=None, placeholder="Obligatoire")
            
            if st.form_submit_button("🚀 Créer la ligne"):
                if p_dep is not None and km_actuel > km_precedent:
                    sheet.append_row([date_j.strftime("%d/%m/%Y"), km_actuel, "", p_dep/100], value_input_option="USER_ENTERED")
                    st.rerun()
                else:
                    st.error("Vérifiez km et batterie.")

with tab_visualisation:
    st.header(f"📊 Dashboard {annee}")
    if st.button("🔄 Actualiser les données"):
        doc = connecter_sheet()
        if doc:
            try:
                sheet = doc.worksheet(f"Recharge {annee}")
                valeurs = sheet.get_all_values()
                if len(valeurs) > 3:
                    df = pd.DataFrame(valeurs[3:], columns=valeurs[2])
                    st.dataframe(df[::-1], use_container_width=True)
            except Exception as e: st.error(str(e))