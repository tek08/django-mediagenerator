from .settings import DEV_MEDIA_URL, MEDIA_DEV_MODE
# Only load other dependencies if they're needed
if MEDIA_DEV_MODE:
    from .utils import _refresh_dev_names, _backend_mapping
    from django.http import HttpResponse, Http404
    from django.utils.cache import patch_cache_control
    from django.utils.http import http_date
    import time
import threading

TEXT_MIME_TYPES = (
    'application/x-javascript',
    'application/xhtml+xml',
    'application/xml',
)

class MediaMiddleware(object):
    """
    Middleware for serving and browser-side caching of media files.

    This MUST be your *first* entry in MIDDLEWARE_CLASSES. Otherwise, some
    other middleware might add ETags or otherwise manipulate the caching
    headers which would result in the browser doing unnecessary HTTP
    roundtrips for unchanged media.
    """

    def __init__(self):
        self.dev_names_set = False
        self.dev_names_lock = threading.Lock()


    def _check_and_maybe_regenerate_dev_map(self):
        """If dev name mapping hasn't been made, make it (thread-safe)."""
        if self.dev_names_lock.acquire():
            if not self.dev_names_set:
                print ""
                print "=" * 30
                print "= Media generator needs to rebuild its index...stand by..."
                print "= "
                print "= Upset about how long this takes? Keep your JS/CSS small!"
                print "=" * 30
                print ""

                _refresh_dev_names()  # only do this first time, others wait
                self.dev_names_set = True

                print ""
                print "=" * 30
                print "= Mediagenerator has finished processing all bundles."
                print "= Now things should be speedy.  Want speedier?"
                print "= keep your JS and CSS bundles small!"
                print "=" * 30
                print ""

            self.dev_names_lock.release()

    MAX_AGE = 60 * 60 * 24 * 365

    def process_request(self, request):
        if not MEDIA_DEV_MODE:
            return

        # We refresh the dev names only once for the whole request, so all
        # media_url() calls are cached.

        self._check_and_maybe_regenerate_dev_map()

        if not request.path.startswith(DEV_MEDIA_URL):
            return

        filename = request.path[len(DEV_MEDIA_URL):]

        try:
            backend = _backend_mapping[filename]
        except KeyError:
            raise Http404('The mediagenerator could not find the media file "%s"'
                          % filename)
        content, mimetype = backend.get_dev_output(filename)
        if not mimetype:
            mimetype = 'application/octet-stream'
        if isinstance(content, unicode):
            content = content.encode('utf-8')
        if mimetype.startswith('text/') or mimetype in TEXT_MIME_TYPES:
            mimetype += '; charset=utf-8'
        response = HttpResponse(content, content_type=mimetype)
        response['Content-Length'] = len(content)

        # Cache manifest files MUST NEVER be cached or you'll be unable to update
        # your cached app!!!
        if response['Content-Type'] != 'text/cache-manifest' and \
                response.status_code == 200:
            patch_cache_control(response, public=True, max_age=self.MAX_AGE)
            response['Expires'] = http_date(time.time() + self.MAX_AGE)
        return response
