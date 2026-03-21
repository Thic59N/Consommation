import subprocess, sys, os

# --- AUTO-INSTALLATION (Sécurisée pour le Cloud) ---
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

# --- FONCTION DE NETTOYAGE ---
def extraire_nombre(valeur):
    if not valeur: return 0.0
    nettoye = "".join(c for c in str(valeur) if c.isdigit() or c in ".,-")
    nettoye = nettoye.replace(',', '.')
    try:
        return float(nettoye)
    except:
        return 0.0

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
    donnees_derniere_ligne = []
    toutes_valeurs = []

    if doc:
        sheet = doc.worksheet(f"Recharge {annee}")
        toutes_valeurs = sheet.get_all_values()
        
        if len(toutes_valeurs) >= 4:
            derniere_ligne = toutes_valeurs[-1]
            num_ligne_active = len(toutes_valeurs)
            
            # Vérification si une charge est déjà commencée (colonne B remplie mais colonne D vide ou manquante)
            if len(derniere_ligne) > 1 and derniere_ligne[1] != "" and (len(derniere_ligne) <= 3 or derniere_ligne[3] == ""):
                charge_en_cours = True
                donnees_derniere_ligne = derniere_ligne

    if charge_en_cours:
        p_depart_detecte = "??"
        if len(toutes_valeurs) >= 4:
            ligne_precedente = toutes_valeurs[num_ligne_active - 2]
            if len(ligne_precedente) > 3:
                val_p = extraire_nombre(ligne_precedente[3])
                p_depart_detecte = int(val_p * 100) if val_p < 1 else val_p

        st.subheader("🏁 Terminer la charge")
        km_affiche = str(donnees_derniere_ligne[1]).replace("km", "").strip()
        st.warning(f"🔋 Débutée le {donnees_derniere_ligne[0]} avec {km_affiche} km et {p_depart_detecte}%")

        with st.form("formulaire_fin_charge"):
            date_fin = st.date_input("Date de fin de charge", datetime.now(), format="DD/MM/YYYY")
            p_fin_saisi = st.number_input("% Batterie final", 0, 100, value=None, placeholder="Ex: 85")
            temps = st.text_input("Temps de recharge (ex: 3:37)", placeholder="H:MM")
            energie = st.number_input("Énergie ajoutée (kWh)", min_value=0.0, step=0.1, value=None)
            
            with st.expander("📍 Modifier Lieu et Prix kWh (Optionnel)"):
                options_lieux = ["Maison", "Borne Publique", "Ionity", "Tesla Supercharger", "Autre..."]
                lieu_selection = st.selectbox("Lieu de recharge", options_lieux)
                lieu_precis = st.text_input("Si Autre, précisez le lieu")
                prix_kwh = st.number_input("Coût en € / kWh", min_value=0.0, value=0.1579, format="%.4f", step=0.0001)

            if st.form_submit_button("✅ Enregistrer la fin de charge"):
                manquants = []
                if p_fin_saisi is None: manquants.append("% Batterie final")
                if not temps: manquants.append("Temps de recharge")
                if energie is None: manquants.append("Énergie ajoutée")
                
                if manquants:
                    st.error(f"⚠️ Champs obligatoires manquants : {', '.join(manquants)}")
                else:
                    lieu_final = lieu_precis if (lieu_selection == "Autre..." and lieu_precis) else lieu_selection
                    p_fin_decimal = p_fin_saisi / 100
                    
                    sheet.update_cell(num_ligne_active, 1, date_fin.strftime("%d/%m/%Y")) # A
                    sheet.update_cell(num_ligne_active, 4, p_fin_decimal)                  # D
                    sheet.update_cell(num_ligne_active, 5, temps)                        # E
                    sheet.update_cell(num_ligne_active, 6, energie)                      # F
                    sheet.update_cell(num_ligne_active, 10, prix_kwh)                    # J
                    sheet.update_cell(num_ligne_active, 12, lieu_final)                   # L
                    
                    st.success(f"Données enregistrées !")
                    st.balloons()
                    st.rerun()

    else:
        st.subheader("🚀 Lancer une nouvelle charge")
        
        # --- CALCUL DU KM PRÉCÉDENT ET SUGGÉRÉ ---
        km_precedent = 0
        km_suggere = 0
        if len(toutes_valeurs) > 3:
            derniere_valeur_km = toutes_valeurs[-1][1]
            km_precedent = extraire_nombre(derniere_valeur_km)
            if km_precedent > 0:
                km_suggere = int(km_precedent // 100) * 100

        with st.form("formulaire_debut"):
            date_j = st.date_input("Date de début de charge", datetime.now(), format="DD/MM/YYYY")
            
            # Champ Kilométrage
            km_actuel = st.number_input("Kilométrage au compteur", min_value=0, value=int(km_suggere))
            
            # Champ % Batterie (Saisie obligatoire, pas de défaut)
            p_dep_saisi = st.number_input("% Batterie au départ", 0, 100, value=None, placeholder="Ex: 20")
            
            if st.form_submit_button("🚀 Créer la nouvelle ligne"):
                erreurs = []
                
                # Vérification Batterie obligatoire
                if p_dep_saisi is None:
                    erreurs.append("Le % de batterie au départ est obligatoire.")
                
                # Vérification Kilométrage (doit être supérieur au précédent réel)
                if km_actuel <= km_precedent:
                    erreurs.append(f"Le kilométrage doit être supérieur au précédent ({int(km_precedent)} km).")
                
                if erreurs:
                    for err in erreurs:
                        st.error(err)
                else:
                    # Tout est bon, on enregistre
                    p_dep_decimal = p_dep_saisi / 100
                    nouvelle_ligne = [date_j.strftime("%d/%m/%Y"), km_actuel, "", p_dep_decimal]
                    sheet.append_row(nouvelle_ligne, value_input_option="USER_ENTERED")
                    st.success("Nouvelle charge enregistrée !")
                    st.rerun()

with tab_visualisation:
    st.header(f"📊 Tableau de bord - {annee}")
    if st.button("🔄 Actualiser les données"):
        doc = connecter_sheet()
        if doc:
            try:
                sheet = doc.worksheet(f"Recharge {annee}")
                valeurs = sheet.get_all_values()
                if len(valeurs) > 3:
                    df = pd.DataFrame(valeurs[3:], columns=valeurs[2])
                    
                    # --- SCORE CARDS ---
                    col_b_brute = [r[1] for r in valeurs[3:] if len(r) > 1]
                    km_total = 0
                    for val in reversed(col_b_brute):
                        n = extraire_nombre(val)
                        if n > 0:
                            km_total = n
                            break

                    col_c_clean = [extraire_nombre(r[2]) for r in valeurs[3:] if len(r) > 2]
                    somme_km = sum(col_c_clean)

                    col_i_clean = [extraire_nombre(r[8]) for r in valeurs[3:] if len(r) > 8]
                    conso_valides = [v for v in col_i_clean if v > 0]
                    avg_conso = sum(conso_valides) / len(conso_valides) if conso_valides else 0.0

                    try:
                        j1_val_brute = sheet.cell(1, 10, value_render_option='UNFORMATTED_VALUE').value
                        j1_val = extraire_nombre(j1_val_brute)
                        if j1_val == 0:
                             j1_val = extraire_nombre(sheet.acell('J1').value)
                        cout_100 = avg_conso * j1_val
                    except:
                        j1_val = 0.0
                        cout_100 = 0.0

                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Km Total (Compteur)", f"{km_total:,.0f} km".replace(',', ' '))
                    c2.metric("Somme Km parcourus", f"{somme_km:,.0f} km".replace(',', ' '))
                    c3.metric("Moyenne Conso", f"{avg_conso:.2f} kWh/100Km")
                    c4.metric(label="Coût au 100km", value=f"{cout_100:.2f} €", delta=f"Prix kWh : {j1_val:.4f}€", delta_color="normal")
                    
                    st.dataframe(df[::-1], use_container_width=True)
                else:
                    st.warning("Pas assez de données.")
            except Exception as e:
                st.error(f"Erreur : {e}")