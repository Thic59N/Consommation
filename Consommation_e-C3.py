import subprocess, sys, os
import json

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
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True
    st.title("🔐 Accès Citroën ë-C3")
    password = st.text_input("Veuillez saisir le mot de passe :", type="password")
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
        parts = t.split(':')
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return h * 60 + m
    except: return 0

def minutes_vers_temps(total_min):
    h = total_min // 60
    m = total_min % 60
    return f"{h}:{m:02d}"

# --- CONNEXION ---
def connecter_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    sheet_id = "1O2bv779GffFziT9TKcfLgRtYLahKsJ7liNncQM7j-gg"
    try:
        service_account_info = st.secrets.get("gcp_service_account")
        if service_account_info is not None:
            info = dict(service_account_info)
            if "private_key" in info:
                info["private_key"] = info["private_key"].replace("\\n", "\n")
            creds = Credentials.from_service_account_info(info, scopes=scope)
        else:
            path_json = os.path.join(os.path.dirname(__file__), "credentials.json")
            if os.path.exists(path_json):
                creds = Credentials.from_service_account_file(path_json, scopes=scope)
            else:
                st.error("⚠️ Identifiants Google Sheets manquants.")
                return None
        client = gspread.authorize(creds)
        return client.open_by_key(sheet_id)
    except Exception as e:
        st.error(f"Erreur connexion : {e}")
        return None

# --- UI PRINCIPALE ---
col_img, col_txt, col_a, col_d = st.columns([1, 2.5, 2, 0.8])
with col_img:
    try:
        img_path = os.path.join(os.path.dirname(__file__), "Citroen eC3.png")
        image = Image.open(img_path) if os.path.exists(img_path) else None
        if image: st.image(image, use_container_width=True)
        else: st.write("🚗")
    except: st.write("🚗")

with col_txt:
    st.markdown("<h3 style='margin-top: 10px;'>Citroën ë-C3</h3>", unsafe_allow_html=True)

with col_a:
    st.markdown("<div style='margin-top: 15px;'>", unsafe_allow_html=True)
    annee = st.selectbox("Année", ["2025", "2026"], index=1, label_visibility="collapsed")
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
    if doc:
        try:
            sheet = doc.worksheet(f"Recharge {annee}")
            valeurs = sheet.get_all_values()
            
            # DÉTECTION ÉTAT : 
            charge_en_cloture = False
            if len(valeurs) >= 4:
                derniere = valeurs[-1]
                # Si la colonne 1 (Km) est remplie mais colonne 5 (Temps) est vide, c'est une ligne de départ
                if len(derniere) >= 2 and derniere[1] != "" and (len(derniere) <= 4 or derniere[4] == ""):
                    charge_en_cloture = True
                    ligne_depart_data = derniere

            if charge_en_cloture:
                st.info(f"🔋 Départ enregistré : {ligne_depart_data[1]} km ({ligne_depart_data[3]})")
                st.subheader("🏁 Fin de la recharge (Nouvelle ligne)")
                
                date_f = st.date_input("Date de fin", datetime.now(), format="DD/MM/YYYY")
                p_fin = st.number_input("% Batterie final *", 0, 100, value=None)
                
                st.markdown("---")
                st.markdown("#### 🧮 Calculs")
                c1, c2 = st.columns(2)
                with c1:
                    st.write("**Temps (H:MM)**")
                    t1 = st.text_input("Session 1 *", "0:00")
                    t2 = st.text_input("Session 2", "")
                    t3 = st.text_input("Session 3", "")
                    t4 = st.text_input("Session 4", "")
                    if st.button("⏱️ Valider Temps"):
                        total_min = sum([temps_vers_minutes(t) for t in [t1, t2, t3, t4]])
                        st.session_state['temps_final_c3'] = minutes_vers_temps(total_min)
                
                with c2:
                    st.write("**Énergie (kWh)**")
                    e1 = st.number_input("Énergie 1 *", 0.0, step=0.1, value=None)
                    e2 = st.number_input("Énergie 2", 0.0, step=0.1)
                    e3 = st.number_input("Énergie 3", 0.0, step=0.1)
                    e4 = st.number_input("Énergie 4", 0.0, step=0.1)
                    if st.button("🔌 Valider Énergie"):
                        total_e = sum([en if en is not None else 0.0 for en in [e1, e2, e3, e4]])
                        st.session_state['energie_finale_c3'] = round(total_e, 2)

                res_t = st.session_state.get('temps_final_c3', "0:00")
                res_e = st.session_state.get('energie_finale_c3', 0.0)
                
                if 'temps_final_c3' in st.session_state or 'energie_finale_c3' in st.session_state:
                    st.success(f"Résumé validé : {res_t} | {res_e} kWh")

                with st.form("form_fin_reel"):
                    with st.expander("📍 Station & Coût (Optionnel)"):
                        lieu = st.selectbox("Station", ["Maison", "Borne Publique", "Ionity", "Tesla", "Autre"])
                        prix_kwh = st.number_input("Coût du kWh (€)", value=0.1600, format="%.4f")
                    
                    if st.form_submit_button("✅ ENREGISTRER LA LIGNE DE FIN"):
                        if p_fin is None or 'temps_final_c3' not in st.session_state or 'energie_finale_c3' not in st.session_state:
                            st.error("⚠️ Veuillez remplir le % final et valider les calculs (Temps et Énergie).")
                        else:
                            # IMPORTANT : On utilise append_row pour créer une NOUVELLE ligne
                            # On reprend le kilométrage de la ligne de départ (index 1)
                            new_row_fin = [
                                date_f.strftime("%d/%m/%Y"), 
                                ligne_depart_data[1],               # On garde le même kilométrage
                                "",                                 # Col C vide
                                f"{p_fin}%",                        # Col D % fin
                                res_t,                              # Col E Temps
                                str(res_e).replace('.', ','),       # Col F Energie
                                "", "", "",                         # Col G, H, I calculées par Sheets
                                str(prix_kwh).replace('.', ','),    # Col J Prix/kWh
                                "",                                 # Col K
                                lieu                                # Col L Lieu
                            ]
                            sheet.append_row(new_row_fin, value_input_option="USER_ENTERED")
                            
                            for k in ['temps_final_c3', 'energie_finale_c3']:
                                if k in st.session_state: del st.session_state[k]
                            
                            st.success("Nouvelle ligne de fin ajoutée !")
                            st.rerun()
            else:
                st.subheader("🚀 Nouvelle charge (Ligne de départ)")
                with st.form("form_depart"):
                    last_km_val = extraire_nombre(valeurs[-1][1]) if len(valeurs) > 3 else 0
                    km_default = int((last_km_val // 100) * 100)
                    
                    date_d = st.date_input("Date", datetime.now(), format="DD/MM/YYYY")
                    km_v = st.number_input(f"Kilométrage actuel (Précédent : {int(last_km_val)}) *", value=km_default)
                    p_dep = st.number_input("% Batterie départ *", 0, 100, value=None)
                    
                    if st.form_submit_button("📝 ENREGISTRER LA LIGNE DE DÉPART"):
                        if p_dep is None:
                            st.error("⚠️ Veuillez saisir le % de batterie.")
                        elif km_v < last_km_val:
                            st.error(f"⚠️ Le kilométrage ne peut pas être inférieur au précédent ({int(last_km_val)} km).")
                        else:
                            row_dep = [
                                date_d.strftime("%d/%m/%Y"), 
                                km_v, 
                                "",              
                                f"{p_dep}%", 
                                "",              # Temps vide -> Signal charge en cours
                                ""               # Energie vide
                            ]
                            sheet.append_row(row_dep, value_input_option="USER_ENTERED")
                            st.success("Ligne de départ ajoutée !")
                            st.rerun()
        except Exception as e:
            st.error(f"Erreur technique : {e}")

with tab_visualisation:
    st.subheader("📊 Statistiques")
    doc = connecter_sheet()
    if doc:
        try:
            sheet = doc.worksheet(f"Recharge {annee}")
            valeurs = sheet.get_all_values()
            if len(valeurs) > 3:
                rows = valeurs[3:]
                col_km = [extraire_nombre(r[1]) for r in rows if len(r) > 1]
                total_km_an = (col_km[-1] - col_km[0]) if len(col_km) > 1 else 0
                col_conso = [extraire_nombre(r[8]) for r in rows if len(r) > 8 and extraire_nombre(r[8]) > 0]
                moy_conso = sum(col_conso) / len(col_conso) if col_conso else 0.0
                col_cout_100 = [extraire_nombre(r[12]) for r in rows if len(r) > 12 and extraire_nombre(r[12]) > 0]
                moy_cout_100 = sum(col_cout_100) / len(col_cout_100) if col_cout_100 else 0.0

                c1, c2, c3 = st.columns(3)
                c1.metric("Somme Km", f"{total_km_an:,.0f} km".replace(',', ' '))
                c2.metric("Moy. Conso", f"{moy_conso:.1f} kWh/100")
                c3.metric("Coût/100km", f"{moy_cout_100:.2f} €")

                st.divider()
                df = pd.DataFrame(rows, columns=valeurs[2])
                st.dataframe(df[::-1], use_container_width=True)
        except:
            st.info("Chargement des données en cours...")