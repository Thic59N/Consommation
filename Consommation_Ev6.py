import subprocess, sys, os
from datetime import datetime, timedelta

# --- AUTO-INSTALLATION ---
def install_requirements():
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
            
            # LOGIQUE : Si on a un KM (Col B / Index 1) mais PAS de % (Col D / Index 3)
            if len(derniere_ligne) > 1 and derniere_ligne[1] != "" and (len(derniere_ligne) <= 3 or derniere_ligne[3] == ""):
                charge_en_cours = True
                donnees_derniere_ligne = derniere_ligne

    # --- AFFICHAGE DES FORMULAIRES ---
    if charge_en_cours:
        # --- LOGIQUE POUR TROUVER LE % DE DÉPART (Ligne précédente) ---
        p_depart_detecte = "??"
        if len(toutes_valeurs) >= 4:
            # On regarde la ligne d'AVANT la ligne active
            ligne_precedente = toutes_valeurs[num_ligne_active - 2]
            if len(ligne_precedente) > 3:
                p_depart_detecte = ligne_precedente[3]

        st.subheader("🏁 Terminer la charge")
        # On nettoie les variables pour éviter les doubles unités (km km ou %%)
        km_affiche = str(donnees_derniere_ligne[1]).replace("km", "").strip()
        p_affiche = str(p_depart_detecte).replace("%", "").strip()

        # Affichage propre
        st.warning(f"🔋 Débutée le {donnees_derniere_ligne[0]} avec {km_affiche} km et {p_affiche}%")

        with st.form("formulaire_fin_charge"):
            # % Batterie final
            p_fin = st.number_input("% Batterie final", min_value=0, max_value=100, value=None, placeholder="Ex: 85")
            
            # Temps de recharge
            temps = st.text_input("Temps de recharge (HH:MM)", placeholder="Ex: 01:30")
            
            # Énergie en kWh
            energie = st.number_input("Énergie ajoutée (kWh)", min_value=0.0, step=0.1, value=None, placeholder="Ex: 45.5")
            
            # Lieu de recharge
            options_lieux = ["Maison", "Borne Publique", "Ionity", "Tesla Supercharger", "Autre..."]
            lieu_selection = st.selectbox("Lieu de recharge", options_lieux)
            
            # Champ texte supplémentaire si "Autre..." est choisi
            lieu_precis = st.text_input("Si Autre, précisez le lieu", placeholder="Nom de la station...")
            
            # Coût du kWh
            prix_kwh = st.number_input("Coût du kWh (€)", min_value=0.0, max_value=2.0, value=0.1579, format="%.4f", step=0.0001)

            # Bouton de validation
            submit = st.form_submit_button("✅ Enregistrer la fin de charge")
            
            if submit:
                if p_fin is None or energie is None or not temps:
                    st.error("⚠️ Les champs % Final, Temps et Énergie sont obligatoires.")
                else:
                    # Choix du nom du lieu
                    lieu_final = lieu_precis if lieu_selection == "Autre..." else lieu_selection
                    
                    # Calcul du coût total
                    cout_total = energie * prix_kwh
                    
                    # Mise à jour des colonnes dans le Sheet (D, F, G, H, I)
                    sheet.update_cell(num_ligne_active, 4, p_fin)      # D : % Fin
                    sheet.update_cell(num_ligne_active, 6, lieu_final) # F : Lieu
                    sheet.update_cell(num_ligne_active, 7, cout_total) # G : Prix Total
                    sheet.update_cell(num_ligne_active, 8, energie)    # H : Energie
                    sheet.update_cell(num_ligne_active, 9, temps)      # I : Temps
                    
                    st.success(f"Données enregistrées ! Coût : {cout_total:.2f} €")
                    st.balloons()
                    st.rerun()

    else:
        # --- BLOC NOUVELLE RECHARGE ---
        st.subheader("1. Lancer une nouvelle charge")
        with st.form("formulaire_debut"):
            date_j = st.date_input("Date de début de charge", datetime.now())
            km_actuel = st.number_input("Kilométrage au compteur", min_value=0, step=1)
            p_dep = st.number_input("% Batterie au départ", 0, 100, value=20)
            
            if st.form_submit_button("🚀 Créer la nouvelle ligne"):
                if km_actuel > 0:
                    nouvelle_ligne = [date_j.strftime("%d/%m/%Y"), km_actuel, "", p_dep]
                    sheet.append_row(nouvelle_ligne, value_input_option="USER_ENTERED")
                    st.success("Ligne créée ! À demain pour la suite.")
                    st.rerun()
                else:
                    st.error("Veuillez indiquer le kilométrage.")

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
                    
                    def extraire_nombre(valeur):
                        if not valeur: return 0.0
                        nettoye = "".join(c for c in str(valeur) if c.isdigit() or c in ".,-")
                        nettoye = nettoye.replace(',', '.')
                        try:
                            return float(nettoye)
                        except:
                            return 0.0

                    # --- CALCULS ---
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

                    # --- AFFICHAGE ---
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Km Total (Compteur)", f"{km_total:,.0f} km".replace(',', ' '))
                    c2.metric("Somme Km parcourus", f"{somme_km:,.0f} km".replace(',', ' '))
                    c3.metric("Moyenne Conso", f"{avg_conso:.2f} kWh/100Km")
                    c4.metric(
                        label="Coût au 100km", 
                        value=f"{cout_100:.2f} €",
                        delta=f"Prix kWh : {j1_val:.4f}€",
                        delta_color="normal"
                    )
                    
                    st.dataframe(df[::-1], use_container_width=True)
                else:
                    st.warning("Pas assez de données.")
            except Exception as e:
                st.error(f"Erreur : {e}")