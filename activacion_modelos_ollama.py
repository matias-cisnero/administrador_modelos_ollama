import tkinter as tk
from tkinter import ttk, messagebox
import requests
import threading
from datetime import datetime, timezone

# --- Configuración ---
OLLAMA_BASE_URL = "http://localhost:11434"
CHAT_MODEL_KEYWORDS = {"llama", "mixtral", "gemma", "phi3", "qwen", "codellama"}


class OllamaManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Control de Modelos Ollama")
        self.root.geometry("550x400") # Ancho aumentado para la nueva información
        self.root.iconbitmap("favicon.ico")

        # Almacenará el estado de todos los modelos
        self.model_statuses = {}

        self.style = ttk.Style()
        self.style.theme_use('clam')

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        list_label = ttk.Label(main_frame, text="Modelos Instalados (Nombre y Estado):")
        list_label.pack(fill=tk.X, pady=(0, 5))

        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Usamos una fuente monoespaciada para alinear el texto en columnas
        self.model_listbox = tk.Listbox(list_frame, height=10, exportselection=False, font=("Courier New", 10))
        self.scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.model_listbox.yview)
        self.model_listbox.config(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.model_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        self.refresh_button = ttk.Button(button_frame, text="Actualizar Lista", command=self.threaded_refresh_list)
        self.refresh_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.load_button = ttk.Button(button_frame, text="Prender (keep_alive: -1)", command=lambda: self.threaded_send_keep_alive(-1))
        self.load_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.unload_button = ttk.Button(button_frame, text="Apagar (keep_alive: 1s)", command=lambda: self.threaded_send_keep_alive("1s"))
        self.unload_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        self.status_var = tk.StringVar(value="Listo.")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding="5")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.threaded_refresh_list()
        self.update_countdown_display() # Inicia el bucle de actualización de la UI

    def get_selected_model_name(self):
        try:
            selected_index = self.model_listbox.curselection()[0]
            # Extraemos solo el nombre del modelo de la línea de texto
            full_text = self.model_listbox.get(selected_index)
            return full_text.split()[0]
        except (IndexError, AttributeError):
            messagebox.showwarning("Sin Selección", "Por favor, selecciona un modelo de la lista.")
            return None

    def threaded_refresh_list(self):
        self.status_var.set("Actualizando lista y estados...")
        threading.Thread(target=self.fetch_and_update_models, daemon=True).start()

    def fetch_and_update_models(self):
        try:
            # 1. Obtener todos los modelos instalados
            tags_response = requests.get(f"{OLLAMA_BASE_URL}/api/tags")
            tags_response.raise_for_status()
            installed_models = tags_response.json().get("models", [])
            
            # 2. Obtener los modelos en ejecución
            ps_response = requests.get(f"{OLLAMA_BASE_URL}/api/ps")
            ps_response.raise_for_status()
            running_models_data = ps_response.json().get("models", [])
            running_models = {model['name']: model for model in running_models_data}

            # 3. Combinar la información
            statuses = {}
            for model in sorted(installed_models, key=lambda x: x['name']):
                name = model['name']
                if name in running_models:
                    statuses[name] = running_models[name]
                else:
                    statuses[name] = {'name': name, 'expires_at': '0001-01-01T00:00:00Z'}
            
            self.model_statuses = statuses
            self.root.after(0, self.status_var.set, "Lista y estados actualizados.")
            
        except requests.exceptions.RequestException as e:
            self.root.after(0, self.show_connection_error, e)

    def update_countdown_display(self):
            """Actualiza la UI cada segundo sin llamar a la API."""
            try:
                selected_indices = self.model_listbox.curselection()
                
                self.model_listbox.delete(0, tk.END)
                for name, status in self.model_statuses.items():
                    expires_at_str = status.get('expires_at', '0001-01-01T00:00:00Z')
                    
                    # --- INICIO DE LA CORRECCIÓN ---
                    # Algunas versiones de Ollama devuelven nanosegundos, Python solo soporta microsegundos.
                    # Aquí truncamos la cadena si tiene más de 6 decimales.
                    if '.' in expires_at_str:
                        parts = expires_at_str.split('.', 1)
                        main_part = parts[0]
                        subsecond_part = parts[1].replace('Z', '').rstrip('+00:00')

                        if len(subsecond_part) > 6:
                            subsecond_part = subsecond_part[:6] # Truncar a 6 dígitos
                        
                        expires_at_str = f"{main_part}.{subsecond_part}Z"
                    # --- FIN DE LA CORRECCIÓN ---

                    if '.' in expires_at_str:
                        expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
                    else:
                        expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00')).replace(tzinfo=timezone.utc)

                    now = datetime.now(timezone.utc)
                    time_left = expires_at - now

                    if expires_at.year < 2000:
                        status_text = "No cargado"
                    elif time_left.total_seconds() > 365 * 24 * 3600:
                        status_text = "Permanente"
                    elif time_left.total_seconds() <= 0:
                        status_text = "Expirado"
                    else:
                        minutes, seconds = divmod(int(time_left.total_seconds()), 60)
                        status_text = f"Expira en {minutes}m {seconds}s"
                    
                    display_string = f"{name:<35} {status_text}"
                    self.model_listbox.insert(tk.END, display_string)
                
                if selected_indices:
                    self.model_listbox.selection_set(selected_indices)

            finally:
                self.root.after(1000, self.update_countdown_display)

    def show_connection_error(self, error):
        self.status_var.set("Error de conexión.")
        messagebox.showerror("Error de Conexión", f"No se pudo conectar con Ollama.\nError: {error}")

    def threaded_send_keep_alive(self, duration):
        model_name = self.get_selected_model_name()
        if not model_name:
            return

        action = "cargando" if duration == -1 else "descargando"
        self.status_var.set(f"Preparando solicitud para {action} '{model_name}'...")
        
        thread = threading.Thread(target=self.send_request, args=(model_name, duration), daemon=True)
        thread.start()

    def send_request(self, model_name, duration):
        is_chat_model = any(keyword in model_name.lower() for keyword in CHAT_MODEL_KEYWORDS)
        
        if is_chat_model:
            endpoint = "/api/chat"
            payload = { "model": model_name, "keep_alive": duration, "messages": [{"role": "user", "content": "Hi"}], "stream": False }
        else:
            endpoint = "/api/generate"
            payload = { "model": model_name, "keep_alive": duration, "prompt": "Hi", "stream": False }

        url = f"{OLLAMA_BASE_URL}{endpoint}"
        try:
            requests.post(url, json=payload, timeout=600)
            self.root.after(500, self.threaded_refresh_list) # Esperar un poco y refrescar
        except requests.exceptions.RequestException as e:
            self.root.after(0, messagebox.showerror, "Error de API", f"Ocurrió un error: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = OllamaManagerApp(root)
    root.mainloop()