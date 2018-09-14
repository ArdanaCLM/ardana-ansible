# (c) Copyright 2017-2018 SUSE LLC

import os
import urllib2
import json
from contextlib import closing
import socket
import sys
if sys.version_info.major < 3:
    from urlparse import urlparse
else:
    from urllib.parse import urlparse

class CallbackModule(object):

    """
    callback plugin sends events to the ardana-service so that other components
    can listen to ansible events, particular playbook starts/stops

    """
    def __init__(self):
        self.srvcurl = 'http://localhost:9085'
        self.timeout = 5  # 5 seconds
        # ardana-service runs on the deployer:9085 by default

    def updateSrvcUrl(self):
        """ Updates the service url to one advertised by the VIP
            but only if the corresponding port is connectable
        """
        hosts = self.playbook.inventory.get_hosts()
        if(hosts):
            try:
                host_vars = \
                    self.playbook.inventory.get_variables(hosts[0].name)
                url = \
                    host_vars['ARD_SVC']['advertises'][
                        'vips']['private'][0]['url']
                purl = urlparse(url)
                with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
                    s.connect((purl.hostname, purl.port))
                    self.srvcurl = url
            except (KeyError, TypeError, socket.error) as error:
                # leave the existing URL in place if the key isnt found
                pass

    def playbook_on_task_start(self, name, is_conditional):
        """Triggers callbacks other services if a specific play was run
          Since playbooks are being run in a nested fashion, only
          the top level playbook will trigger playbook_on_stats
          indicating that its finished (the same is true for
          playbook_on_start). Instead, fake the start/finish
          events by injecting a start and finish task into
          important playbooks, and parse for that task here
        """
        callbacks_map = {
            'pbfinish.yml pb_finish_playbook': 'stop',
            'pbstart.yml pb_start_playbook': 'start'
        }
        playbook_name = self.task.play_vars.get('playbook_name', None)
        if playbook_name is not None and name in callbacks_map:
            self.post_to_listener(playbook_name, callbacks_map[name])

    # function called when playbook is started
    # calls back to the ardana service indicating a playbook start
    def playbook_on_start(self):
        self.post_to_listener(self.playbook.filename, 'start')

    # function called when playbook is finished
    # calls back to the ardana service indicating a playbook stop
    def playbook_on_stats(self, stats):
        action = 'stop'
        if(len(stats.dark) + len(stats.failures) > 0):
            action = 'error'
        self.post_to_listener(self.playbook.filename, action)

    def post_to_listener(self, playbook, action):
        self.updateSrvcUrl()
        urlpath = '/api/v2/listener/playbook'
        url = self.srvcurl + urlpath
        try:
            data = json.dumps({
                'play_id': os.environ['PLAY_ID'],
                'event': action,
                'playbook': playbook
             })
            req = urllib2.Request(url, data,
                                  {'Content-type': 'application/json'})
            f = urllib2.urlopen(req)
            response = f.read()
        except Exception as ex:
            # nothing to do on exception, probably means the URL is incorrect
            # or not available for the playbook in question
            pass
