# Certbot NGINX Unit plugin #

This is a certbot plugin for using certbot in combination with NGINX Unit https://unit.nginx.org/

## Requirement ##

The command `unitc` should be installed and executable. 

## Current Features ##

* Supports NGINX Unit/1.31*
* Supports cerbot 2.12+ / 3+
* install certificates
* automatic renewal certificates

## Installation ##

* Via Snap (requires certbot to be installed via snap):

    install [snapd](https://snapcraft.io/docs/installing-snapd)
    
    install certbot
    ```
    snap install --classic certbot
    ```
    install and configure this plugin
    ```
    sudo snap install certbot-nginx-unit 
    sudo snap set certbot trust-plugin-with-root=ok
    sudo snap connect certbot:plugin certbot-nginx-unit
    ```

* Via Pip
    ```
    pip install certbot certbot-nginx-unit
    ```

* Via Pip virtual env

    Create a virtual environment, to avoid conflicts
    ```
    python3 -m venv /some/path
    ```

    use the pip in the virtual environment to install or update

    ```
    /some/path/bin/pip install -U certbot certbot-nginx-unit
    ```

    use the cerbot from the virtualenv, to avoid accidentally
    using one from a different environment that does not have this library
    ```
    /some/path/bin/certbot
    ```

    or uninstall other certbot system installation and link it to /usr/bin
    ```
    ln -s /some/path/bin/certbot /usr/bin
    ```

## Usage ##

Configure the unit listener with `*:80` or `*:443`

```
# unitc /config
```
```
{
    "listeners": {
        "*:80": {
            "pass": "routes"
        }
        "routes": [
            {
                "action": {
                    "share": "/srv/www/unit/index.html"
                }
            }
        ]
    }
}
```

Now, generate and automatically install the certificate with

```
# certbot --configurator nginx-unit -d www.myapp.com
```

The result is a certificate created and installed. 

```
# unitc /certificates
```

```
{
	"www.myapp.com_20240202145800": {
		"key": "RSA (2048 bits)",
		"chain": [
			{
				<omissis>
			}
		]
	}
}
```
and the configuration updated

```
# unitc /config
```

```
{
	"listeners": {
		"*:80": {
			"pass": "routes"
		},

		"*:443": {
			"pass": "routes",
			"tls": {
				"certificate": [
					"www.myapp.com_20240202145800"
				]
			}
		}
	},

	"routes": [
		{
			"match": {
				"uri": "/.well-known/acme-challenge/*"
			},

			"action": {
				"share": "/srv/www/unit/$uri"
			}
		},
		{
			"action": {
				"share": "/srv/www/unit/index.html"
			}
		}
	]
}
```

## Auto-renew certificates ##

Certbot installs a timer on the system to renew certificates one month before the certificate expiration date.

## Multiple domains/applications ## 

You can run the certbot command for each domain

```
# certbot --configurator nginx-unit -d www.myapp1.com
# certbot --configurator nginx-unit -d www.myapp2.com
# unitc '/config/listeners/*:443' 
```

```
{
    "pass": "routes",
    "tls": {
        "certificate": [
            "www.myapp1.com_20240202145800"
            "www.myapp2.com_20240202145800"
        ]
    }
}
```

