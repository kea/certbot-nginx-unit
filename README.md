Certbot NGINX Unit plugin
=========================

This is a certbot plugin for using certbot in combination with NGINX Unit https://unit.nginx.org/

Current Features
=====================

* Supports NGINX Unit/1.31*
* Supports cerbot 1.21+
* automatic install certificates

Install
=======

You have to install the plugin and configure the unit listener for port 80

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

Now you can generate and automatic install the certificate with
```
# certbot --configurator nginx_unit -d www.myapp.com
```
The results is a certificate created and installed 

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