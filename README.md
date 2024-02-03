Certbot NGINX Unit plugin
=========================

This is a certbot plugin for using certbot in combination with NGINX Unit https://unit.nginx.org/

Requirement
===========
The command `unitc` should be installed and executable. 

Current Features
=====================

* Supports NGINX Unit/1.31*
* Supports cerbot 1.21+
* install certificates
* automatic renewal certificates

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

Now, you can generate and automatically install the certificate with

```
# certbot --configurator nginx_unit -d www.myapp.com
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

Auto-renew certificates
=======================

Certbot installs a timer on the system to renew certificates one month before the certificate expiration date.

Multiple domains/applications
=============================

You can run the certbot command for each domain

```
# certbot --configurator nginx_unit -d www.myapp1.com
# certbot --configurator nginx_unit -d www.myapp2.com
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

