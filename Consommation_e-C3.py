import subprocess, sys, os

# --- AUTO-INSTALLATION ---
def install_requirements():
    if os.environ.get("STREAM_RUNTIME_EXECUTION_MODE") is None:
        packages = ["streamlit", "gspread", "google-auth", "pandas", "Pillow"]
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
from PIL import Image

# --- CONFIG PAGE ---
st.set_page_config(page_title="Consommation Citroën ë-C3", layout="wide")

# --- AUTHENTIFICATION ---
def check_password():
    """Retourne True si l'utilisateur a saisi le bon mot de passe."""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    st.title("🔐 Accès Citroën ë-C3")
    password = st.text_input("Veuillez saisir le mot de passe :", type="password")
    
    # Récupération sécurisée via les secrets Streamlit
    target_password = st.secrets.get("auth", {}).get("password", "admin") 

    if st.button("Connexion"):
        if password == target_password:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("🚫 Mot de passe incorrect.")
    return False

if not check_password():
    st.stop()

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
    
    # ID corrigé (celui qui fonctionnait précédemment pour la ë-C3)
    sheet_id = "1O2bv779GffFziT9TKcfLgRtYLahKsJ7liNncQM7j-gg"
    
    try:
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        else:
            path_json = os.path.join(os.path.dirname(__file__), "credentials.json")
            if os.path.exists(path_json):
                creds = Credentials.from_service_account_file(path_json, scopes=scope)
            else:
                st.error("⚠️ Identifiants Google Sheets manquants.")
                return None
        
        client = gspread.authorize(creds)
        return client.open_by_key(sheet_id)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"🚫 Erreur 404 : Fichier Google Sheet introuvable. Vérifiez l'ID et que le fichier est PARTAGÉ avec l'email du compte de service.")
        return None
    except Exception as e:
        st.error(f"Erreur connexion : {e}")
        return None

# --- UI PRINCIPALE (BANNER) ---
col_img, col_txt, col_a, col_d = st.columns([1, 2.5, 2, 0.8])

with col_img:
    try:
        img_path = os.path.join(os.path.dirname(__file__), "Citroen eC3.png")
        if os.path.exists(img_path):
            image = Image.open(img_path)
            st.image(image, use_container_width=True)
        else:
            st.write("🚗")
    except:
        st.write("🚗")

with col_txt:
    st.markdown("<h3 style='margin-top: 10px;'>Citroën ë-C3</h3>", unsafe_allow_html=True)

with col_a:
    st.markdown("<div style='margin-top: 15px;'>", unsafe_allow_html=True)
    
    # Sélection automatique de l'année par défaut
    options_annee = ["2025", "2026"]
    annee_actuelle = str(datetime.now().year)
    index_defaut = options_annee.index(annee_actuelle) if annee_actuelle in options_annee else 0
    
    annee = st.selectbox("Année", options_annee, index=index_defaut, label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)

with col_d:
    st.markdown("<div style='margin-top: 15px;'>", unsafe_allow_html=True)
    if st.button("🚪"):
        st.session_state["password_correct"] = False
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

st.divider()

tab_saisie, tab_visualisation = st.tabs(["📝 Saisie", "📊 Infos"])

with tab_saisie:
    doc = connecter_sheet()
    charge_en_cours = False
    num_ligne_active = None
    toutes_valeurs = []

    if doc:
        try:
            sheet = doc.worksheet(f"Recharge {annee}")
            toutes_valeurs = sheet.get_all_values()
            if len(toutes_valeurs) >= 4:
                derniere_ligne = toutes_valeurs[-1]
                num_ligne_active = len(toutes_valeurs)
                # Détection charge en cours : km présents mais pas de % fin (colonne 4) ou de kWh (colonne 6)
                if len(derniere_ligne) > 1 and derniere_ligne[1] != "" and (len(derniere_ligne) <= 5 or derniere_ligne[5] == ""):
                    charge_en_cours = True
                    donnees_derniere_ligne = derniere_ligne
        except Exception as e:
            st.error(f"Erreur onglet 'Recharge {annee}': {e}")
            doc = None

    if doc:
        if charge_en_cours:
            st.info(f"🔋 Charge en cours : {donnees_derniere_ligne[1]} km")

            date_fin = st.date_input("Date fin", datetime.now(), format="DD/MM/YYYY")
            p_fin_saisi = st.number_input("% Batterie final *", 0, 100, value=None)

            st.divider()
            st.markdown("#### 🧮 Calculs Octopus")
            
            c_t, c_e = st.columns(2)
            with c_t:
                st.write("**Temps (H:MM)**")
                t1 = st.text_input("Sess. 1 *", key="calc_t1")
                t2 = st.text_input("Sess. 2", key="calc_t2")
                if st.button("⏱️ Valider"):
                    total_min = sum([temps_vers_minutes(t) for t in [t1, t2]])
                    st.session_state['temps_final'] = minutes_vers_temps(total_min)

            with c_e:
                st.write("**Énergie (kWh)**")
                en1 = st.number_input("kWh 1 *", min_value=0.0, step=0.01, key="calc_e1")
                en2 = st.number_input("kWh 2", min_value=0.0, step=0.01, key="calc_e2")
                if st.button("🔌 Valider"):
                    tot_e = sum([en if en is not None else 0.0 for en in [en1, en2]])
                    st.session_state['energie_finale'] = round(tot_e, 2)

            t_final = st.session_state.get('temps_final', "0:00")
            e_final = st.session_state.get('energie_finale', 0.0)
            
            if 'temps_final' in st.session_state or 'energie_finale' in st.session_state:
                st.success(f"Résumé : {t_final} | {e_final} kWh")

            with st.form("save_final"):
                lieu = st.selectbox("Lieu", ["Maison", "Borne Publique", "Ionity", "Tesla Supercharger", "Autre..."])
                prix = st.number_input("Coût €/kWh", value=0.1579, format="%.4f")
                
                if st.form_submit_button("✅ CLÔTURER LA RECHARGE"):
                    if p_fin_saisi is None or 'temps_final' not in st.session_state or 'energie_finale' not in st.session_state:
                        st.warning("Veuillez valider les calculs (Temps et Énergie).")
                    else:
                        sheet.update_cell(num_ligne_active, 1, date_fin.strftime("%d/%m/%Y"))
                        sheet.update_cell(num_ligne_active, 4, p_fin_saisi / 100)
                        sheet.update_cell(num_ligne_active, 5, t_final)
                        sheet.update_cell(num_ligne_active, 6, e_final)
                        sheet.update_cell(num_ligne_active, 10, prix)
                        sheet.update_cell(num_ligne_active, 12, lieu)
                        
                        for k in ['temps_final', 'energie_finale']:
                            if k in st.session_state: del st.session_state[k]
                        st.rerun()

        else:
            with st.form("form_debut"):
                st.subheader("🚀 Nouvelle recharge")
                
                # Calcul du kilométrage suggéré (centaine inférieure)
                km_precedent = extraire_nombre(toutes_valeurs[-1][1]) if len(toutes_valeurs) > 3 else 0
                km_suggere = (int(km_precedent) // 100) * 100
                
                date_j = st.date_input("Date", datetime.now(), format="DD/MM/YYYY")
                
                # Affichage avec espace pour les milliers
                km_label = f"Kilométrage actuel (Dernier : {int(km_precedent):,})".replace(',', ' ')
                km_actuel = st.number_input(km_label, value=km_suggere, step=1)
                
                p_dep = st.number_input("% Batterie départ *", 0, 100, value=None)
                
                if st.form_submit_button("DÉMARRER"):
                    if p_dep is None:
                        st.error("⚠️ Le champ '% Batterie départ' est obligatoire.")
                    else:
                        sheet.append_row([date_j.strftime("%d/%m/%Y"), km_actuel, "", p_dep/100], value_input_option="USER_ENTERED")
                        st.rerun()

with tab_visualisation:
    st.subheader("📊 Historique & Stats")
    doc = connecter_sheet()
    if doc:
        try:
            sheet = doc.worksheet(f"Recharge {annee}")
            valeurs = sheet.get_all_values()
            if len(valeurs) > 3:
                # --- CALCULS STATS ---
                # On récupère tous les kilométrages valides
                col_km = [extraire_nombre(r[1]) for r in valeurs[3:] if len(r) > 1 and extraire_nombre(r[1]) > 0]
                
                km_actuel = col_km[-1] if col_km else 0
                km_depart = col_km[0] if col_km else 0
                somme_km = km_actuel - km_depart if len(col_km) > 1 else 0
                
                # On récupère les consommations (colonne I / Index 8)
                col_conso = [extraire_nombre(r[8]) for r in valeurs[3:] if len(r) > 8 and extraire_nombre(r[8]) > 0]
                avg_conso = sum(col_conso) / len(col_conso) if col_conso else 0.0
                
                # On récupère les prix (colonne J / Index 9)
                col_prix = [extraire_nombre(r[9]) for r in valeurs[3:] if len(r) > 9 and extraire_nombre(r[9]) > 0]
                avg_prix = sum(col_prix) / len(col_prix) if col_prix else 0.1579
                
                # Coût pour 100km
                cout_100 = (avg_conso * avg_prix)

                # --- AFFICHAGE SCORE CARDS ---
                m1, m2, m3 = st.columns(3)
                m1.metric("Somme Km", f"{somme_km:,.0f} km".replace(',', ' '))
                m2.metric("Moy. Conso", f"{avg_conso:.1f} kWh/100")
                m3.metric("Coût/100km", f"{cout_100:.2f} €")

                st.divider()
                
                # Historique inversé (plus récent en haut)
                df = pd.DataFrame(valeurs[3:], columns=valeurs[2])
                st.dataframe(df[::-1], use_container_width=True)
                
                st.caption(f"Compteur actuel : {km_actuel:,.0f} km".replace(',', ' '))
        except Exception as e:
            st.warning(f"Données Sheets introuvables ou erreur : {e}")