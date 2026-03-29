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
    """Nettoie la chaîne (ex: '21%') pour retourner un float (21.0)."""
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
            else:
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
            
            charge_en_cours = False
            ligne_data = None
            idx_ligne = -1
            
            # 1. On cherche la ligne "en cours" (KM présent, Temps absent)
            for i in range(len(valeurs) - 1, 2, -1):
                l = valeurs[i]
                if len(l) >= 2 and l[1].strip() != "": # Si KM présent
                    if len(l) <= 4 or not l[4].strip(): # Si Temps absent
                        charge_en_cours = True
                        ligne_data = l
                        idx_ligne = i # Index 0-based pour la liste valeurs
                        break
                    else:
                        break 

            if charge_en_cours:
                # 2. RÉCUPÉRATION DU KM DE DÉPART (sur la ligne en cours)
                km_depart_val = extraire_nombre(ligne_data[1])
                
                # 3. RÉCUPÉRATION DU % DE DÉPART (SUR LA LIGNE PRÉCÉDENTE)
                # On prend la ligne juste au dessus (idx_ligne - 1)
                p_depart_val = 0.0
                if idx_ligne > 3: # On vérifie qu'on n'est pas sur les entêtes
                    ligne_precedente = valeurs[idx_ligne - 1]
                    # La batterie est en colonne D (index 3)
                    if len(ligne_precedente) > 3:
                        p_depart_val = extraire_nombre(ligne_precedente[3])
                
                st.subheader("🏁 Fin de la recharge")
                
                p_cible = st.number_input("% souhaité", 0, 100, value=85)
                diff = max(0, p_cible - p_depart_val)
                
                st.info(
                    f"🔋 **KM de départ :** {int(km_depart_val):,} km".replace(',', ' ') + 
                    f"\n\n⚡ **% batterie à ajouter : {int(diff)}%** (Calcul basé sur **{int(p_depart_val)}%** au départ)"
                )
                
                date_f = st.date_input("Date de fin", datetime.now(), format="DD/MM/YYYY")
                p_fin = st.number_input("% Batterie final *", 0, 100, value=None, placeholder="Ex: 85")
                
                st.markdown("---")
                st.markdown("#### 🧮 Calculs")
                c1, c2 = st.columns(2)
                with c1:
                    st.write("**Temps (H:MM)**")
                    t1 = st.text_input("Sess. 1 *", value="", placeholder="ex: 2:38")
                    t2 = st.text_input("Sess. 2", value="")
                    t3 = st.text_input("Sess. 3", value="")
                    t4 = st.text_input("Sess. 4", value="")
                    if st.button("⏱️ Valider Temps"):
                        total_m = sum([temps_vers_minutes(t) for t in [t1, t2, t3, t4]])
                        st.session_state['c3_t_res'] = minutes_vers_temps(total_m)
                
                with c2:
                    st.write("**Énergie (kWh)**")
                    e1 = st.number_input("kWh 1 *", 0.0, step=0.1, value=None)
                    e2 = st.number_input("kWh 2", 0.0, step=0.1, value=None)
                    e3 = st.number_input("kWh 3", 0.0, step=0.1, value=None)
                    e4 = st.number_input("kWh 4", 0.0, step=0.1, value=None)
                    if st.button("🔌 Valider Énergie"):
                        total_e = sum([en if en is not None else 0.0 for en in [e1, e2, e3, e4]])
                        st.session_state['c3_e_res'] = round(total_e, 2)

                st.markdown(
                    f"<div style='background-color: #1e2130; padding: 10px; border-radius: 5px; border-left: 5px solid #ff4b4b; margin-top: 10px;'>"
                    f"📊 <b>Résumé :</b> Temps {st.session_state.get('c3_t_res', '0:00')} | Énergie {st.session_state.get('c3_e_res', 0.0)} kWh"
                    f"</div>", 
                    unsafe_allow_html=True
                )

                with st.form("cloture_form"):
                    lieu = st.selectbox("Lieu", ["Maison", "Borne Publique", "Ionity", "Tesla", "Autre"])
                    prix = st.number_input("Coût €/kWh", value=0.1579, format="%.4f")
                    
                    if st.form_submit_button("✅ ENREGISTRER LA FIN"):
                        if p_fin is None or 'c3_t_res' not in st.session_state:
                            st.error("⚠️ Manque % final ou calculs.")
                        else:
                            # Mise à jour de la ligne (idx_ligne + 1 car gspread commence à 1)
                            ligne_reelle = idx_ligne + 1
                            sheet.update_cell(ligne_reelle, 1, date_f.strftime("%d/%m/%Y"))
                            sheet.update_cell(ligne_reelle, 4, f"{p_fin}%")
                            sheet.update_cell(ligne_reelle, 5, st.session_state['c3_t_res'])
                            sheet.update_cell(ligne_reelle, 6, str(st.session_state['c3_e_res']).replace('.', ','))
                            sheet.update_cell(ligne_reelle, 10, str(prix).replace('.', ','))
                            sheet.update_cell(ligne_reelle, 12, lieu)
                            
                            for k in ['c3_t_res', 'c3_e_res']:
                                if k in st.session_state: del st.session_state[k]
                            st.success("Recharge clôturée !")
                            st.rerun()
            else:
                st.subheader("🚀 Nouvelle charge")
                # Aide KM
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
                    st.info(f"⚡ **Batterie à ajouter : {int(p_souhait - p_dep_saisie)}%**")

                if st.button("📝 ENREGISTRER LE DÉPART"):
                    if p_dep_saisie is None:
                        st.error("⚠️ Saisir le % actuel.")
                    else:
                        km_v = int(extraire_nombre(km_in))
                        # IMPORTANT: On enregistre le % de départ dans la colonne D (index 4)
                        # pour qu'il soit disponible lors de la clôture
                        sheet.append_row([date_d.strftime("%d/%m/%Y"), km_v, "", f"{p_dep_saisie}%", "", ""], value_input_option="USER_ENTERED")
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