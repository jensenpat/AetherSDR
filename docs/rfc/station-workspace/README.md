# Station workspace connection RFC illustrations

Canon dark-theme design concepts, captured from the interactive mockup.
All radios, availability labels, accounts and profiles are sample data.
These images describe a proposal; they are not evidence that the desktop
application implements or has validated the proposed behavior.

| Illustration | Purpose |
|---|---|
| `home.png` | One station containing FlexRadio, Hermes-Lite 2 and RTL-SDR |
| `pota.png` | Portable Icom and HL2 connection setups |
| `cabin.png` | Remote FlexRadio through a saved SmartLink account |
| `profile-selection.png` | Select an operator profile independently of station and account |
| `profile-creation.png` | Create an operator profile from an existing profile or defaults |
| `station-creation.png` | Create a station profile |
| `smartlink-accounts.png` | Shared account references and independent sign-in status |

`mockup.html` is the editable HTML fragment used for the captures. It uses
only local sample state and does not connect to radios or authenticate
accounts. Profile creation is demonstrated locally in that sample state.
Other save and authentication actions are illustrative.

Visual reference: `docs/style/aethersdr-style-guide.md`, `CanonWindow` and
the `color.canon.*` / `color.brand.gradient` palette. Desktop implementation
must use ThemeManager tokens and the existing Canon window components.

The source shows an appearance toggle when hosted with the optional Tweak
helper; the RFC screenshots use Canon dark. No application dependency is
introduced by these design assets.
