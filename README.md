Certbot NGINX Unit plugin
=========================

This is a certbot plugin for using certbot in combination with NGINX Unit https://unit.nginx.org/

Current Features
=====================

* Supports NGINX Unit/1.31*
* automatic install certificates

Install
=======

After you have installed the plugin and have configured the unit listener for port 80 and 443 (https://unit.nginx.org/howto/certbot/#generating-certificates)

In the listeners section the `*:80` is for the webroot certification generation and the `*:443` part is for the application and for storing the name of the certificate.

```
# unitc /config
```
```
{
    "listeners": {
        "*:80": {
            "pass": "routes/acme"
        },
        "*:443": {
            "pass": "applications/myapp",
            "tls": {
                "certificate": []
            }
        }
    },

    "routes": {
        "acme": [
            {
                "match": {
                    "uri": "/.well-known/acme-challenge/*"
                },

                "action": {
                    "share": "/var/www/www.example.com/"
                }
            }
        ]
    }
    "applications": {
        "myapp": {
            "type": "python",
            "module": "wsgi",
            "path": "/usr/www/wsgi-app/"
        }
    }
}
```

Now you can generate and automatic install the certificate with
```
# certbot -a webroot -w /www/certbot/ -i nginx_unit_installer -d www.myapp.com
```