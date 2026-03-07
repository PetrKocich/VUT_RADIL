import streamlit as st
from mistralai import Mistral
from qdrant_client import QdrantClient

# --- NASTAVENÍ ---
API_KEY = st.secrets["MISTRAL_API_KEY"]

client = Mistral(api_key=API_KEY)
qdrant = QdrantClient(path="./moje_vektory_produkce") 

# --- HLAVNÍ OKNO ---
st.title("🎓 VUT Chatbot RADIL-1")
st.markdown("Paar rad do začátku? Zeptejte se na cokoliv ze studijních materiálů. Zvládám státnicové předměty Elektroenergetiky (DEE, EEE, RZB, SUE, TMB a VEE)")

# --- INICIALIZACE PAMĚTI PRO VÍCE CHATŮ ---
if "chats" not in st.session_state:
    # Vytvoříme slovník pro ukládání různých konverzací
    st.session_state.chats = {"Konverzace 1": [{"role": "assistant", "content": "Dobrý den! Jsem váš AI tutor. S čím začneme?"}]}
if "current_chat" not in st.session_state:
    st.session_state.current_chat = "Konverzace 1"

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



# Vykreslení historie zpráv AKTUALNĚ VYBRANÉHO chatu
aktivni_historie = st.session_state.chats[st.session_state.current_chat]

for message in aktivni_historie:
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

        # HLEDÁNÍ VE VŠECH PŘEDMĚTECH (Filtr byl odebrán)
        vysledky = qdrant.query_points(
            collection_name="skripta_vut",
            query=dotaz_vektor,
            limit=3
        ).points

    with st.chat_message("assistant"):
        if vysledky:
            nalezeny_text = ""
            zdroje_info = []
            
            for v in vysledky:
                payload = v.payload
                predmet = payload['metadata'].get('Predmet', 'Neznámý')
                nalezeny_text += f"[{predmet}]: {payload['text']}\n\n"
                zdroje_info.append(f"**{predmet}**: {payload['metadata']}")

            # Historie pro API (posledních 5 zpráv z aktuálního chatu)
            historie_pro_llm = st.session_state.chats[st.session_state.current_chat][-5:] 
            
            # --- DYNAMICKÝ PROMPT PODLE ZVOLENÉHO REŽIMU ---
            if rezim == "📖 Vysvětlování látky":
                kontext = f"""Jsi expertní AI tutor pro studenty VUT.
                Zde jsou relevantní úryvky z oficiálních skript:
                {nalezeny_text}
                
                VÁ PRAVIDLA:
            1. Odpovídej POUZE na základě poskytnutých skript. Pokud tam odpověď není, řekni to.
            2. Vysvětluj látku pedagogicky, jasně a strukturovaně a do hloubky na vysokoškolské úrovni. Vždy uváděj konktrétní hodnoty které jsou pro kompletnost odpovědí podstatné. Nezjednušuj pokud si to uživatel nevyžádá.
            3. Maximální dodržování přesnosti odpovědí, hlídej si kontext a NIKDY nemíchej dvě různá témata pokud se uživatel doptává dál, Vždy si skontroluj pravdivost návaznosti a nikdy si nevymýšlej. Pokud otázka směřuje k tématu které nemáš ve skriptech zodpovězenou, odpověď nerozvíjej a v odpovědi strikně uveď že se nejedná o znalost ze skript.
            4. Pokud odpověď není striktě dána ve skriptech, neodpovídej a zeptej se uživatele co přesně myslí a nabídni mu další pomoc.
            5. Pokud se k tomu téma vybízí, nabídni uživateli několik možností dalších otázek k tématu které mu dokážeš zodpovědět.
            6. STRIKTNÍ FORMÁTOVÁNÍ MATEMATIKY: Všechny rovnice a proměnné musí být v LaTeXu pomocí znaku dolaru.
               - Proměnná v textu: $x$
               - Samostatná rovnice: $$y = x^2$$
               ZAKÁZÁNO je používat závorky jako \( \) nebo \[ \].
            """

            else:
                # REŽIM ZKOUŠENÍ (Nová logika!)
                kontext = f"""Jsi přísný, ale spravedlivý zkoušející profesor na VUT.
                Zde jsou relevantní úryvky z oficiálních skript k tématu, na které se student ptá:
                {nalezeny_text}
                
                TVÁ PRAVIDLA PRO ZKOUŠENÍ:
                1. NEDÁVEJ STUDENTOVI PŘÍMOU ODPOVĚĎ! Tím bys zkazil zkoušení.
                2. Na základě úryvků ze skript vymysli pro studenta 1-2 těžší záludné otázky, abys ověřil, že dané pasáži rozumí.
                3. Pokud student ve svém promptu odpovídá na tvou předchozí otázku, zhodnoť jeho odpověď podle skript, řekni mu, co měl špatně, a polož další otázku.
                4. Buď profesionální, povzbuzuj, ale vyžaduj přesné termíny ze skript.
                5. Využívej LaTeX pro matematiku.
                """
            
            zpravy_pro_api = [{"role": "system", "content": kontext}] + historie_pro_llm

            with st.spinner("Formuluji odpověď..."):
                chat_response = client.chat.complete(
                    model="mistral-small-latest",
                    messages=zpravy_pro_api,
                    temperature=0.0 if rezim == "📖 Vysvětlování látky" else 0.4 # Při zkoušení může být trochu kreativnější ve vymýšlení otázek
                )
                odpoved = chat_response.choices[0].message.content
            
            st.markdown(odpoved)
            
            with st.expander("📚 Zobrazit podklady pro tuto konverzaci"):
                for zdroj in zdroje_info:
                    st.write(zdroj)

        else:
            odpoved = "Omlouvám se, ale k tomuto tématu jsem v žádných skriptech nenašel informace."
            st.markdown(odpoved)

        # Uložení odpovědi do aktuální konverzace
        st.session_state.chats[st.session_state.current_chat].append({"role": "assistant", "content": odpoved})