# SSO & SAML Identity Provider Setup

Image Dataset Curator integrates with Keycloak as its OIDC Identity Provider (IdP). Keycloak in turn supports upstream enterprise SAML 2.0 Identity Providers (such as Okta, Azure Active Directory / Entra ID, PingFederate, or Google Workspace) via identity brokering.

## 1. Keycloak Realm Setup

The pre-configured realm import file is located at `keycloak/realm-export.json`.
When running with Docker Compose:

```bash
docker compose up -d keycloak
```

Keycloak automatically imports the `curator` realm on initial container startup using `--import-realm`.

### Roles Defined
- **`viewer`**: Read-only access to datasets and image galleries.
- **`analyst`**: Can upload images, run duplicate detection, assign splits, and export manifests.
- **`admin`**: Full administrative access including deleting datasets and images.

---

## 2. Upstream SAML IdP Brokering Configuration

To connect an enterprise SAML 2.0 provider:

1. **Log in to Keycloak Admin Console**:
   Navigate to `http://localhost:8080/admin` and log in with your admin credentials.

2. **Select Realm**:
   Switch to the **`curator`** realm.

3. **Add Identity Provider**:
   - Go to **Identity Providers** in the left sidebar.
   - Choose **SAML v2.0**.
   - Provide an **Alias** (e.g. `enterprise-saml` or `okta-saml`).
   - Import the SAML metadata from your corporate IdP URL or XML file.

4. **Service Provider (SP) Metadata**:
   - Keycloak generates SP metadata at:
     `http://localhost:8080/realms/curator/broker/{alias}/endpoint/descriptor`
   - Register this URL / metadata with your upstream SAML IdP.

5. **Attribute & Role Mappers**:
   - Go to **Mappers** under the created SAML Identity Provider.
   - Map SAML assertion attributes:
     - `email` -> user attribute `email`
     - `given_name` -> user attribute `firstName`
     - `surname` -> user attribute `lastName`
     - `groups` or `roles` -> **SAML Attribute to Role** mapper to map groups to `analyst` or `admin`.

---

## 3. Application Authentication Flow

1. User clicks **Sign In** in the frontend React application.
2. The browser redirects to backend `/api/auth/login`.
3. The backend generates a secure state, nonce, and PKCE challenge (S256), then redirects to Keycloak.
4. Keycloak presents the corporate login (or redirects directly to the configured SAML IdP).
5. After successful SAML assertion validation, Keycloak issues authorization code to the backend callback.
6. The backend exchanges the code and PKCE verifier for tokens with Keycloak, validates claims/nonce, and sets an HttpOnly `session_token` cookie.
7. Mutating requests are guarded by session cookies, CSRF tokens, and role-based checks.
