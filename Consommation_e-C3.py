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

# --- FONCTIONS DE NETTOYAGE ---
def extraire_nombre(valeur):
    if valeur is None or valeur == "": return 0.0
    valeur_str = str(valeur).strip()
    nettoye = "".join(c for c in valeur_str if c.isdigit() or c in ".,")
    nettoye = nettoye.replace(',', '.')
    try: 
        return float(nettoye)
    except: 
        return 0.0

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

# --- CONNEXION GOOGLE SHEETS ---
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
            else: return None
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
            
            charge_en_cours = False
            ligne_data = None
            idx_ligne = -1
            
            for i in range(len(valeurs) - 1, 2, -1):
                l = valeurs[i]
                if len(l) >= 2 and l[1].strip() != "":
                    if len(l) <= 4 or not l[4].strip():
                        charge_en_cours = True
                        ligne_data = l
                        idx_ligne = i
                        break
                    else: break 

            if charge_en_cours:
                # --- INFOS DE DÉPART ---
                km_depart_val = extraire_nombre(ligne_data[1])
                p_depart_val = 0.0
                if idx_ligne > 0:
                    ligne_precedente = valeurs[idx_ligne - 1]
                    if len(ligne_precedente) > 3:
                        p_depart_val = extraire_nombre(ligne_precedente[3])
                
                # --- CALCUL DYNAMIQUE HORS FORMULAIRE ---
                st.subheader("🏁 Fin de la recharge")
                st.info(f"🔋 **KM de départ :** {int(km_depart_val):,} km".replace(',', ' ') + 
                        f"  \n⚡ **Batterie au départ : {int(p_depart_val)}%**")
                
                # Nombre de sessions HORS formulaire pour être dynamique
                nb_sessions = st.number_input("Nombre de sessions de charge", min_value=1, max_value=20, value=4)
                
                with st.form("form_fin"):
                    p_fin = st.number_input("% Batterie final *", 0, 100, value=None, placeholder="Ex: 85")
                    date_f = st.date_input("Date de fin", datetime.now(), format="DD/MM/YYYY")
                    
                    st.markdown("#### 🧮 Détails des sessions")
                    c1, c2 = st.columns(2)
                    t_inputs = []
                    e_inputs = []
                    
                    with c1:
                        st.write("**Temps (H:MM)**")
                        for i in range(nb_sessions):
                            label = f"Sess. {i+1} *" if i == 0 else f"Sess. {i+1}"
                            val_t = st.text_input(label, value="", placeholder="Ex: 2:38", key=f"t_in_{i}")
                            t_inputs.append(val_t)
                    
                    with c2:
                        st.write("**Énergie (kWh)**")
                        for i in range(nb_sessions):
                            label = f"kWh {i+1} *" if i == 0 else f"kWh {i+1}"
                            val_e = st.number_input(label, 0.0, step=0.1, value=None, key=f"e_in_{i}")
                            e_inputs.append(val_e)

                    st.markdown("---")
                    # Boutons de calculs optionnels restaurés dans le formulaire
                    if st.form_submit_button("⏱ / 🔌 CALCULER LES TOTAUX (Optionnel)"):
                        total_m_preview = sum([temps_vers_minutes(t) for t in t_inputs])
                        total_e_preview = sum([en if en is not None else 0.0 for en in e_inputs])
                        if total_m_preview > 0: st.success(f"⏱ Total Temps : {minutes_vers_temps(total_m_preview)}")
                        if total_e_preview > 0: st.success(f"🔌 Total Énergie : {total_e_preview:.2f} kWh")

                    with st.expander("📍 Lieu et Tarification", expanded=False):
                        lieu_base = st.selectbox("Lieu", ["Maison", "Borne Publique", "Ionity", "Tesla", "Autre"])
                        lieu_autre = st.text_input("Si Autre, précisez")
                        prix = st.number_input("Coût €/kWh", value=0.1579, format="%.4f")

                    btn_finir = st.form_submit_button("✅ ENREGISTRER LA FIN ET FERMER")

                if btn_finir:
                    if p_fin is None or not t_inputs[0] or e_inputs[0] is None:
                        st.error("⚠️ Veuillez remplir les champs obligatoires (*) pour enregistrer.")
                    else:
                        total_m = sum([temps_vers_minutes(t) for t in t_inputs])
                        t_res = minutes_vers_temps(total_m)
                        total_e = sum([en if en is not None else 0.0 for en in e_inputs])
                        lieu_final = lieu_autre if lieu_base == "Autre" and lieu_autre else lieu_base
                        ligne_reelle = idx_ligne + 1
                        
                        sheet.update_cell(ligne_reelle, 1, date_f.strftime("%d/%m/%Y"))
                        sheet.update_cell(ligne_reelle, 4, f"{p_fin}%")
                        sheet.update_cell(ligne_reelle, 5, t_res)
                        sheet.update_cell(ligne_reelle, 6, str(round(total_e, 2)).replace('.', ','))
                        sheet.update_cell(ligne_reelle, 10, str(prix).replace('.', ','))
                        sheet.update_cell(ligne_reelle, 12, lieu_final)

                        try:
                            sheet_octopus = doc.worksheet("Octopus")
                            dates_octo = sheet_octopus.col_values(1)
                            row_octo = len(dates_octo) 
                            sheet_octopus.update_cell(row_octo, 4, f"{p_fin}%")
                            sheet_octopus.update_cell(row_octo, 6, str(round(total_e, 2)).replace('.', ','))
                        except:
                            pass
                        
                        st.success("Recharge enregistrée !")
                        st.rerun()

            else:
                # --- NOUVELLE CHARGE ---
                st.subheader("🚀 Nouvelle charge")
                last_km = 0
                for r in valeurs[3:]:
                    if len(r) > 1 and extraire_nombre(r[1]) > 0:
                        last_km = int(extraire_nombre(r[1]))
                
                date_d = st.date_input("Date", datetime.now(), format="DD/MM/YYYY")
                km_in = st.text_input(f"Kilométrage (Dernier : {last_km})", value=f"{last_km:,}".replace(',', ' '))
                
                c1, c2 = st.columns(2)
                with c1:
                    p_dep_saisie = st.number_input("% actuel *", 0, 100, value=None)
                with c2:
                    p_souhait = st.number_input("% souhaité", 0, 100, value=85)

                if p_dep_saisie is not None:
                    diff_debut = max(0, p_souhait - p_dep_saisie)
                    st.info(f"⚡ **Batterie à ajouter : {int(diff_debut)}%**")

                if st.button("📝 ENREGISTRER LE DÉPART"):
                    if p_dep_saisie is None:
                        st.error("⚠️ Saisir le % actuel.")
                    else:
                        km_v = int(extraire_nombre(km_in))
                        date_str = date_d.strftime("%d/%m/%Y")
                        diff_debut = max(0, p_souhait - p_dep_saisie)
                        
                        sheet.append_row([date_str, km_v, "", f"{p_dep_saisie}%", "", ""], value_input_option="USER_ENTERED")
                        
                        try:
                            sheet_octopus = doc.worksheet("Octopus")
                            new_row_octo = [date_str, f"{diff_debut}%", f"{p_souhait}%", ""]
                            sheet_octopus.append_row(new_row_octo, value_input_option="USER_ENTERED")
                        except Exception as e:
                            st.warning(f"Note: Impossible de mettre à jour l'onglet Octopus ({e})")

                        st.success("Départ enregistré !")
                        st.rerun()

        except Exception as e:
            st.error(f"Erreur : {e}")

with tab_visualisation:
    doc = connecter_sheet()
    if doc:
        try:
            sheet = doc.worksheet(f"Recharge {annee}")
            valeurs = sheet.get_all_values()
            if len(valeurs) > 3:
                df = pd.DataFrame(valeurs[3:], columns=valeurs[2])
                st.dataframe(df[::-1], use_container_width=True)
        except:
            st.info("Données non trouvées.")