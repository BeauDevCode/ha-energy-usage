# Providers

Energy Usage separates its Home Assistant entities, ledger, statistics, and diagnostics from utility-specific authentication and response parsing. Each provider adapter must declare its measurements, currency, interval duration, publication delay, historical range, and minimum polling interval. Unsupported measurements stay absent rather than appearing as zero.

## Available in 0.1.0-rc.1

| Provider | Country | Locations | Measurements | Status |
| --- | --- | --- | --- | --- |
| Entergy | United States | One selected service location | Positive imported energy; cost only when the source supplies validated USD | Release candidate |

Entergy is the only available provider in the first release. Its account interface is unofficial and may change without notice. Interactive MFA, CAPTCHA, consent, and unknown redirects are unsupported and fail closed. Do not weaken account security to make the adapter work.

The reviewed Entergy response contains one signed net-usage value rather than independent import and return series. Negative net hours are left unknown; they are not converted into returned energy. Negative signed cost is not treated as compensation. Cost is retained only when the same source interval explicitly supplies a validated USD currency.

## Provider roadmap

Future United States utilities can be added only through separate reviewed adapters. A candidate adapter needs synthetic fixtures, bounded fixed-origin transport, privacy review, capability and correction tests, licensing review, and a maintainer who can validate it without committing production data. There is no release date or coverage promise for another utility.

Adding an adapter must not change the public `energy_usage` domain or the pseudonymous statistics format. Version 1 still allows one configured provider account and one service location, even if more adapters become available later.
