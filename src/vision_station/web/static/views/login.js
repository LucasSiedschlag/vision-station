import { html, useState, useEffect, useRef } from '../lib.js';
import { Dialog, Field, Button, toast } from '../ui.js';
import { login } from '../api.js';
import { ROLE_LABEL, describeError } from '../viewmodel.js';

export function LoginDialog({ onClose }) {
  const [role, setRole] = useState('supervisor');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const field = useRef(null);
  useEffect(() => field.current && field.current.focus(), []); // a dialog drawn after load does not autofocus by itself

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await login(role, password);
      toast(`Entrou como ${ROLE_LABEL[role]}`, 'ok');
      onClose();
    } catch (err) {
      setError(err.status === 429 ? 'Muitas tentativas. Aguarde um pouco.' : err.status === 401 ? 'Perfil ou senha incorretos.' : describeError(err));
    } finally {
      setBusy(false);
      setPassword('');
    }
  }

  return html`<${Dialog} title="Entrar" onClose=${onClose}>
    <form onSubmit=${submit} class="form">
      <${Field} label="Perfil">
        <select value=${role} onChange=${(e) => setRole(e.target.value)}>
          <option value="supervisor">${ROLE_LABEL.supervisor}</option>
          <option value="maintainer">${ROLE_LABEL.maintainer}</option>
        </select>
      <//>
      <${Field} label="Senha">
        <input type="password" autocomplete="current-password" ref=${field} value=${password} onInput=${(e) => setPassword(e.target.value)} />
      <//>
      ${error ? html`<p class="form-error" role="alert">${error}</p>` : null}
      <div class="dialog-actions">
        <${Button} type="button" onClick=${onClose}>Cancelar<//>
        <${Button} type="submit" tone="primary" busy=${busy} disabled=${!password}>Entrar<//>
      </div>
    </form>
  <//>`;
}
