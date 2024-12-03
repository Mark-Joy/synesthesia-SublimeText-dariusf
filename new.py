import sublime, sublime_plugin
import os, tempfile, webbrowser
from . import templates
from . import compile

class SynesthesiaNewCommand(sublime_plugin.WindowCommand):
	def run(self):
		if (int(sublime.version()) < 4000):
			v = self.window.new_file(syntax = 'Packages/JavaScript/JSON.tmLanguage')
		else:
			v = self.window.new_file(syntax = 'Packages/JSON/JSON.sublime-syntax')
		v.settings().set('default_dir', compile.SYNESTHESIA_OUTPUT_PATH)
		v.run_command("insert_snippet", {"contents": templates.new_file})

class SynesthesiaSampleCommand(sublime_plugin.WindowCommand):
	def run(self):
		if (int(sublime.version()) < 4000):
			v = self.window.new_file(syntax = 'Packages/JavaScript/JSON.tmLanguage')
		else:
			v = self.window.new_file(syntax = 'Packages/JSON/JSON.sublime-syntax')
		v.settings().set('default_dir', compile.SYNESTHESIA_OUTPUT_PATH)
		v.run_command("insert_snippet", {"contents": templates.sample_file})
