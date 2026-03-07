import streamlit as st
from mistralai import Mistral
from qdrant_client import QdrantClient

# --- NASTAVENÍ (Zabezpečený klíč) ---
API_KEY = st.secrets["MISTRAL_API_KEY"] # Klíč se bere ze secrets

client = Mistral(api_key=API_KEY)
# Tento kouzelný příkaz řekne Streamlitu: "Načti databázi jen JEDNOU při startu a pak už ji nech otevřenou"
@st.cache_resource
def nacti_databazi():
    return QdrantClient(path="./moje_vektory_produkce")

qdrant = nacti_databazi()

st.set_page_config(page_title="VUT Tutor", page_icon="🎓", layout="wide") 

# --- INICIALIZACE PAMĚTI PRO VÍCE CHATŮ ---
if "chats" not in st.session_state:
    st.session_state.chats = {"Konverzace 1": [{"role": "assistant", "content": "Dobrý den! Jsem váš AI tutor. S čím začneme?"}]}
if "current_chat" not in st.session_state:
    st.session_state.current_chat = "Konverzace 1"

# --- FUNKCE PRO VYLEPŠENÍ ČÍSLO 2: STAŽENÍ CHATU (Formátování textu) ---
def ziskej_text_chatu_pro_export(historie_chatu):
    vystup = "🎓 VÝPIS KONVERZACE Z AI TUTORA VUT\n"
    vystup += "="*40 + "\n\n"
    for msg in historie_chatu:
        autor = "👩‍🏫 TUTOR" if msg["role"] == "assistant" else "👤 STUDENT"
        # Odstraníme ikony, aby to bylo v TXT souboru čistší
        cisty_autor = autor.replace("👩‍🏫 ", "").replace("👤 ", "")
        vystup += f"{cisty_autor}:\n{msg['content']}\n\n"
        vystup += "-"*20 + "\n"
    vystup += "\n(Přeji hodně štěstí u zkoušky!)"
    return vystup

# --- LEVÝ POSTRANNÍ PANEL (SIDEBAR) ---
with st.sidebar:
    st.title("⚙️ Nastavení Tutora")
    
    # PŘEPÍNAČ REŽIMŮ
    rezim = st.radio(
        "Vyberte režim práce:",
        ["📖 Vysvětlování látky", "📝 Zkoušení znalostí"],
        help="V režimu vysvětlování vám Tutor pomůže látku pochopit. V režimu zkoušení vám bude klást kontrolní otázky."
    )
    
    st.divider()
    
    # SPRÁVA HISTORIE CHATŮ
    st.markdown("### 💬 Vaše konverzace")
    
    # Tlačítko pro nový chat
    if st.button("➕ Zahájit nový chat", use_container_width=True):
         nove_jmeno = f"Konverzace {len(st.session_state.chats) + 1}"
         st.session_state.chats[nove_jmeno] = [{"role": "assistant", "content": f"Nová konverzace ({rezim}). Na co se podíváme?"}]
         st.session_state.current_chat = nove_jmeno
         st.rerun()

    # Přepínač mezi existujícími chaty
    vybrany_chat = st.radio(
        "Historie:",
        list(st.session_state.chats.keys()),
        index=list(st.session_state.chats.keys()).index(st.session_state.current_chat)
    )
    
    if vybrany_chat != st.session_state.current_chat:
        st.session_state.current_chat = vybrany_chat
        st.rerun()

    # --- VYLEPŠENÍ ČÍSLO 2: TLAČÍTKO PRO STAŽENÍ ---
    st.divider()
    aktivni_historie = st.session_state.chats[st.session_state.current_chat]
    text_pro_download = ziskej_text_chatu_pro_export(aktivni_historie)
    
    st.download_button(
        label="📥 Stáhnout tuto konverzaci (TXT)",
        data=text_pro_download,
        file_name=f"VUT_Tutor_{st.session_state.current_chat}.txt",
        mime="text/plain",
        use_container_width=True,
        help="Uloží aktuální chat jako čistý textový soubor. Ideální pro výpisky."
    )

# --- HLAVNÍ OKNO ---
# Rozdělíme horní část na dva sloupce: levý (větší) pro text, pravý (menší) pro logo
col1, col2 = st.columns([4, 1]) 

with col1:
    st.title("🎓 Expertní Tutor VUT")
    st.markdown("Paar dobrých rad do začátku? Zeptejte se mě na cokoliv ze studijních materiálů. Zvládám státnicové předměty Elektroenergetiky (DEE, EEE, RZB, SUE, TMB a VEE)")

with col2:
    try:
        # Zkuste načíst logo. Parametr use_container_width zajistí, že se hezky přizpůsobí šířce sloupce
        st.image("logo_ueen.svg", use_container_width=True)
    except FileNotFoundError:
        # Pokud program logo nenajde (např. překlep v názvu), nespadne, jen se nevykreslí
        pass

# Vykreslení historie zpráv AKTUALNĚ VYBRANÉHO chatu
for message in st.session_state.chats[st.session_state.current_chat]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- HLAVNÍ LOGIKA ---
if prompt := st.chat_input("Napište svůj dotaz nebo odpověď sem..."):
    
    # Uložení dotazu do aktuálního chatu
    st.session_state.chats[st.session_state.current_chat].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.spinner("Prohledávám skripta..."):
        dotaz_vektor = client.embeddings.create(
            model="mistral-embed",
            inputs=[prompt]
        ).data[0].embedding

        vysledky = qdrant.query_points(
            collection_name="skripta_vut",
            query=dotaz_vektor,
            limit=3
        ).points

    with st.chat_message("assistant"):
        if vysledky:
            nalezeny_text = ""
            zdroje_info = [] # <-- PŘIDÁNO: Vytvoříme si seznam na ukládání zdrojů
            
            for v in vysledky:
                payload = v.payload
                predmet = payload['metadata'].get('Predmet', 'Neznámý')
                nalezeny_text += f"[{predmet}]: {payload['text']}\n\n"
                
                # <-- PŘIDÁNO: Uložíme si informace o nalezeném zdroji
                zdroje_info.append(f"**Předmět {predmet}**: {payload.get('metadata', '')}")

            # Historie pro API (posledních 5 zpráv)
            historie_pro_llm = st.session_state.chats[st.session_state.current_chat][-5:] 
            
            # --- DYNAMICKÝ PROMPT ---
            if rezim == "📖 Vysvětlování látky":
                kontext = f"""Jsi expertní AI tutor pro studenty elektroenergetiky VUT FEKT. Jsi praktickou částí bakalářské práce autora Petr Kocich pod vedením Doktora Paara na téma Chatbot pro výuku elektroenergetiky. Ty jsi ten chatbot a máš za úkol pouze pomáhat stuentům při studiu. Funguješ na principu databáze RAG pod LLM od francouzské firmy Mistral. Dosahuješ tak optimálního poměru cena výkon a ochrany více než 2000 stránek univerzitních skript
                Zde jsou relevantní úryvky z oficiálních skript:
                {nalezeny_text}
                
                TVÁ PRAVIDLA:
            1. Odpovídej POUZE na základě poskytnutých skript. Pokud tam odpověď není, řekni to.
            2. Vysvětluj látku pedagogicky, jasně a strukturovaně a do hloubky na vysokoškolské úrovni. Vždy uváděj konktrétní hodnoty které jsou pro kompletnost odpovědí podstatné. Nezjednušuj pokud si to uživatel nevyžádá.
            3. Maximální dodržování přesnosti odpovědí, hlídej si kontext a NIKDY nemíchej dvě různá témata pokud se uživatel doptává dál, Vždy si skontroluj pravdivost návaznosti a nikdy si nevymýšlej. Pokud otázka směřuje k tématu které nemáš ve skriptech zodpovězenou, odpověď nerozvíjej a v odpovědi strikně uveď že se nejedná o znalost ze skript.
            4. Pokud odpověď není striktě dána ve skriptech, neodpovídej a zeptej se uživatele co přesně myslí a nabídni mu další pomoc.
            5. Pokud se k tomu téma vybízí, nabídni uživateli několik možností dalších otázek k tématu které mu dokážeš zodpovědět.
            6. STRIKTNÍ FORMÁTOVÁNÍ MATEMATIKY: Všechny rovnice a proměnné musí být v LaTeXu pomocí znaku dolaru.
               - Proměnná v textu: $x$
               - Samostatná rovnice: $$y = x^2$$
               ZAKÁZÁNO je používat závorky jako \( \) nebo \[ \].
            7. Při dotazu na aktuální verzi uveď 1.0 
            """

            else:
                # REŽIM ZKOUŠENÍ
                kontext = f"""Jsi přísný zkoušející profesor na VUT.
                Zde jsou relevantní úryvky z oficiálních skript k tématu:
                {nalezeny_text}
                
                TVÁ PRAVIDLA PRO ZKOUŠENÍ:
                1. NEDÁVEJ STUDENTOVI PŘÍMOU ODPOVĚĎ!
                2. Na základě úryvků vymysli pro studenta 1-2 těžší záludné otázky.
                3. Pokud student odpovídá, zhodnoť jeho odpověď a polož další otázku.
                4. Využívej LaTeX pro matematiku.
                5. STRIKTNÍ FORMÁTOVÁNÍ MATEMATIKY: Všechny rovnice a proměnné musí být v LaTeXu pomocí znaku dolaru.
               - Proměnná v textu: $x$
               - Samostatná rovnice: $$y = x^2$$
               ZAKÁZÁNO je používat závorky jako \( \) nebo \[ \].
            """
            
            zpravy_pro_api = [{"role": "system", "content": kontext}] + historie_pro_llm

            with st.spinner("Formuluji odpověď..."):
                stream_response = client.chat.stream(
                    model="mistral-small-latest",
                    messages=zpravy_pro_api,
                    temperature=0.0 if rezim == "📖 Vysvětlování látky" else 0.4
                )
                
                def vyfiltruj_text():
                    for chunk in stream_response:
                        obsah = chunk.data.choices[0].delta.content
                        if obsah and isinstance(obsah, str):
                            yield obsah
                
                kompletni_odpoved = st.write_stream(vyfiltruj_text())
                
                if not kompletni_odpoved:
                    kompletni_odpoved = "Omlouvám se, při generování textu došlo k drobné technické chybě."
            
            # Jakmile se dotextuje, uložíme to bezpečně do historie
            st.session_state.chats[st.session_state.current_chat].append({"role": "assistant", "content": kompletni_odpoved})
            
            # <-- PŘIDÁNO: Vykreslení rozbalovacího okna se zdroji
            with st.expander("📚 Zobrazit podklady pro tuto odpověď"):
                # Použijeme list(set(...)) pro smazání duplicit (kdyby našel 3 úryvky ze stejného PDF)
                for zdroj in list(set(zdroje_info)):
                    st.write(zdroj)

        else:
            odpoved = "Omlouvám se, ale k tomuto tématu jsem v žádných skriptech nenašel informace."
            st.markdown(odpoved)
            st.session_state.chats[st.session_state.current_chat].append({"role": "assistant", "content": odpoved})