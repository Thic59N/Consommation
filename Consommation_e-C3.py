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
tab_saisie, tab_visualisation = st.tabs(["📝 Saisie", "📊 Historique Sheets"])

with tab_saisie:
    doc = connecter_sheet()
    if doc:
        try:
            sheet = doc.worksheet(f"Recharge {annee}")
            valeurs = sheet.get_all_values()
            
            charge_en_cloture = False
            if len(valeurs) >= 4:
                derniere = valeurs[-1]
                if len(derniere) >= 2 and derniere[1] != "" and (len(derniere) <= 4 or (len(derniere) > 4 and (derniere[4] == "" or derniere[4] is None))):
                    charge_en_cloture = True
                    ligne_depart_data = derniere

            if charge_en_cloture:
                km_depart_propre = int(extraire_nombre(ligne_depart_data[1]))
                st.info(f"🔋 Départ enregistré : {km_depart_propre:,} km".replace(',', ' '))
                st.subheader("🏁 Fin de la recharge")
                
                date_f = st.date_input("Date de fin", datetime.now(), format="DD/MM/YYYY")
                p_fin = st.number_input("% Batterie final *", 0, 100, value=None, placeholder="Ex: 80")
                
                st.markdown("---")
                st.markdown("#### 🧮 Calculs")
                c1, c2 = st.columns(2)
                with c1:
                    st.write("**Temps (H:MM)**")
                    t1 = st.text_input("Sess. 1 *", value="", placeholder="Obligatoire (ex: 2:38)")
                    t2 = st.text_input("Sess. 2", value="", placeholder="Optionnel")
                    t3 = st.text_input("Sess. 3", value="", placeholder="Optionnel")
                    t4 = st.text_input("Sess. 4", value="", placeholder="Optionnel")
                    if st.button("⏱️ Valider Temps"):
                        total_min = sum([temps_vers_minutes(t) for t in [t1, t2, t3, t4]])
                        st.session_state['temps_final_c3'] = minutes_vers_temps(total_min)
                
                with c2:
                    st.write("**Énergie (kWh)**")
                    e1 = st.number_input("kWh 1 *", 0.0, step=0.1, value=None, placeholder="Obligatoire")
                    e2 = st.number_input("kWh 2", 0.0, step=0.1, value=None, placeholder="Optionnel")
                    e3 = st.number_input("kWh 3", 0.0, step=0.1, value=None, placeholder="Optionnel")
                    e4 = st.number_input("kWh 4", 0.0, step=0.1, value=None, placeholder="Optionnel")
                    if st.button("🔌 Valider Énergie"):
                        total_e = sum([en if en is not None else 0.0 for en in [e1, e2, e3, e4]])
                        st.session_state['energie_finale_c3'] = round(total_e, 2)

                # --- RÉSUMÉ DYNAMIQUE ---
                res_t = st.session_state.get('temps_final_c3', "0:00")
                res_e = st.session_state.get('energie_finale_c3', 0.0)
                p_label = f"{p_fin}%" if p_fin is not None else "None%"
                
                st.markdown(
                    f"<div style='background-color: #1e2130; padding: 10px; border-radius: 5px; border-left: 5px solid #ff4b4b; margin-bottom: 20px;'>"
                    f"📊 <b>Résumé :</b> Batterie {p_label} | Temps {res_t} | Énergie {res_e} kWh"
                    f"</div>", 
                    unsafe_allow_html=True
                )

                with st.form("form_fin_reel"):
                    with st.expander("📍 Lieu et Prix (Optionnel)", expanded=False):
                        lieu_select = st.selectbox("Lieu", ["Maison", "Borne Publique", "Ionity", "Tesla", "Autre"])
                        lieu_precis = st.text_input("Si Autre, précisez", placeholder="Optionnel")
                        
                        final_lieu = lieu_precis if lieu_precis and lieu_select == "Autre" else lieu_select
                        prix_kwh = st.number_input("Coût €/kWh", value=0.1579, format="%.4f")
                    
                    if st.form_submit_button("✅ TOUT ENREGISTRER DANS SHEETS"):
                        if p_fin is None or 'temps_final_c3' not in st.session_state or 'energie_finale_c3' not in st.session_state:
                            st.error("⚠️ Veuillez remplir le % final et valider les calculs.")
                        else:
                            num_ligne = len(valeurs)
                            
                            sheet.update_cell(num_ligne, 1, date_f.strftime("%d/%m/%Y"))
                            sheet.update_cell(num_ligne, 4, f"{p_fin}%")
                            sheet.update_cell(num_ligne, 5, res_t)
                            sheet.update_cell(num_ligne, 6, str(res_e).replace('.', ','))
                            sheet.update_cell(num_ligne, 10, str(prix_kwh).replace('.', ','))
                            sheet.update_cell(num_ligne, 12, final_lieu)

                            for k in ['temps_final_c3', 'energie_finale_c3']:
                                if k in st.session_state: del st.session_state[k]
                            st.success("Données enregistrées dans Google Sheets !")
                            st.rerun()
            else:
                st.subheader("🚀 Nouvelle charge")
                with st.form("form_depart"):
                    last_km_val = extraire_nombre(valeurs[-1][1]) if len(valeurs) > 3 else 0
                    km_default_str = f"{int(last_km_val)}"
                    last_km_str = f"{int(last_km_val):,}".replace(',', ' ')
                    
                    date_d = st.date_input("Date", datetime.now(), format="DD/MM/YYYY")
                    km_input_str = st.text_input(f"Kilométrage actuel (Précédent : {last_km_str}) *", value=km_default_str, placeholder="Entrez le kilométrage")
                    p_dep = st.number_input("% Batterie départ *", 0, 100, value=None, placeholder="Ex: 15")
                    
                    if st.form_submit_button("📝 ENREGISTRER LA LIGNE DE DÉPART"):
                        km_v_final = int(extraire_nombre(km_input_str))
                        if p_dep is None:
                            st.error("⚠️ Veuillez saisir le % de batterie.")
                        elif km_v_final < last_km_val:
                            st.error(f"⚠️ Kilométrage incohérent.")
                        else:
                            row_dep = [date_d.strftime("%d/%m/%Y"), km_v_final, "", f"{p_dep}%", "", ""]
                            sheet.append_row(row_dep, value_input_option="USER_ENTERED")
                            st.success("Ligne de départ ajoutée !")
                            st.rerun()
        except Exception as e:
            st.error(f"Erreur : {e}")

with tab_visualisation:
    st.subheader(f"📊 Dashboard {annee}")
    doc = connecter_sheet()
    if doc:
        try:
            sheet = doc.worksheet(f"Recharge {annee}")
            valeurs = sheet.get_all_values()
            if len(valeurs) > 3:
                rows = valeurs[3:]
                col_km = [extraire_nombre(r[1]) for r in rows if len(r) > 1]
                km_total = col_km[-1] if col_km else 0
                total_km_an = (col_km[-1] - col_km[0]) if len(col_km) > 1 else 0
                col_conso = [extraire_nombre(r[8]) for r in rows if len(r) > 8 and extraire_nombre(r[8]) > 0]
                moy_conso = sum(col_conso) / len(col_conso) if col_conso else 0.0
                col_cout_100 = [extraire_nombre(r[12]) for r in rows if len(r) > 12 and extraire_nombre(r[12]) > 0]
                moy_cout_100 = sum(col_cout_100) / len(col_cout_100) if col_cout_100 else 0.0

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Km Total", f"{km_total:,.0f} km".replace(',', ' '))
                c2.metric("Somme Km", f"{total_km_an:,.0f} km".replace(',', ' '))
                c3.metric("Moy. Conso", f"{moy_conso:.2f} kWh/100km")
                c4.metric("Coût/100km", f"{moy_cout_100:.2f} €")
                st.divider()
                df = pd.DataFrame(rows, columns=valeurs[2])
                st.dataframe(df[::-1], use_container_width=True)
        except:
            st.info("Données non disponibles.")