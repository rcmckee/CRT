import flet as ft
########
import docx
import pysos
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import semantic_search
# from google.colab import files
# from IPython.display import HTML
import hashlib
from difflib import SequenceMatcher
# import re
import os
import asyncio
import webbrowser

def main(page: ft.Page):

	cutoff_value = 0.7 # primary similarity threshold, you can lower this to get more results. a number between 1.0 and 0.0
	secondary_cutoff_value = 0.60 # secondary similarity threshold for related clauses.

	# loading pre-made contract codex database
	db_hash_values = pysos.Dict('storage/db/pysos_hash_values')
	db_meta_data = pysos.Dict('storage/db/pysos_meta_data_db')

	# creating sentence embeddings from the contract codex clauses
	# sentence embeddings allow similarity searching
	clause_phrases = [v['clause'] for k,v in db_hash_values.items()]

	model = SentenceTransformer('all-MiniLM-L6-v2')

	sentence_embeddings = model.encode(clause_phrases)

	def get_text_from_file(filename):
		doc = docx.Document(filename)
		fullText = []
		for para in doc.paragraphs:
			try:
				if len(para.text.strip()) > 0:
					fullText.append(para.text)
			except:
				pass
		return fullText


	def get_text_from_pasted_text(text):
		fullText = []
		for para in text.split('\n'):
			try:
				if len(para.strip()) > 0:
					fullText.append(para)
			except:
				pass
		return fullText
	
	
	def hash_text(text):
		hash_object = hashlib.md5(text.encode())
		return hash_object.hexdigest()
	
	def show_redlines(a, b):
		#in pure python instead of redlines package which doesn't work on snowflake
		a_words = a.split()
		b_words = b.split()

		matcher = SequenceMatcher(None, a_words, b_words)
		result = []

		for tag, i1, i2, j1, j2 in matcher.get_opcodes():
			if tag == "equal":
				result.extend(a_words[i1:i2])
			elif tag == "replace":
				result.extend([f"<del>{w}</del>" for w in a_words[i1:i2]])
				result.extend([f"<ins>{w}</ins>" for w in b_words[j1:j2]])
			elif tag == "delete":
				result.extend([f"<del>{w}</del>" for w in a_words[i1:i2]])
			elif tag == "insert":
				result.extend([f"<ins>{w}</ins>" for w in b_words[j1:j2]])

		return ' '.join(result)
	
	def output_results_as_html_string(sentence_being_reviewed, matches):
		sentence_being_reviewed = sentence_being_reviewed.strip()
		match_outline_list = [f'<li>{show_redlines(sentence_being_reviewed,match)}</li></br>' for match in matches]
		match_outline_string = ''.join(match_outline_list)
		#codex_outline = db[db['clauses_to_search'][matches[0]]['maingroup']]['maingroup_subgroups_url'][0]
		codex_outline = db_meta_data[db_hash_values[hash_text(matches[0])]['maingroup']]['maingroup_subgroups_url'][0]
		main_clause_type = codex_outline[0]
		codex_outline = [f'<li>{item}</li>' for item in codex_outline[1:]]
		codex_outline = ''.join(codex_outline)
		#codex_url = db[db['clauses_to_search'][matches[0]]['maingroup']]['maingroup_subgroups_url'][1]
		codex_url = db_meta_data[db_hash_values[hash_text(matches[0])]['maingroup']]['maingroup_subgroups_url'][1]
		try:
			#larger_clause =  f" It may be part of a larger clause:</br>{show_redlines(sentence_being_reviewed, db['clauses_to_search'][matches[0]]['larger_clause'])}"
			larger_clause =  f" It may be part of a larger clause:</br>{show_redlines(sentence_being_reviewed, db_hash_values[db_hash_values[hash_text(matches[0])]['larger_clause']]['clause'])}"
		except:
			larger_clause = ""
		return f'''<h3>{sentence_being_reviewed}</h3>
		<div class="noteBoxes type2">
		<details>
			<summary>Expand Notes</summary>
				{editor}
				{button}
		</details>
	<details>
	<summary>See Analysis</summary>
			<p>The most similar clauses are presented below with track changes to see the difference between your contract clause and the similar clauses.</p>
			<p><ul>
				{match_outline_string}
			</ul></p>
			<p><b><u>EXPLANATION OF THE LANGUAGE</u></b></p>
			<p>This clause resembles a {db_hash_values[hash_text(matches[0])]['maingroup']} and is likely part of a subgroup of the clause labeled {db_hash_values[hash_text(matches[0])]['subgroup']}:</br>{larger_clause}</p>

			<p>Main Group: {db_hash_values[hash_text(matches[0])]['maingroup']}</p>
			<p>Main Group Notes: {db_meta_data[db_hash_values[hash_text(matches[0])]['maingroup']]['maingroup_notes']}</p>

			<p>Sub Group: {db_hash_values[hash_text(matches[0])]['subgroup']}</p>
			<p>Sub Group Notes: {db_meta_data[db_hash_values[hash_text(matches[0])]['maingroup']]['sub_groups'][db_hash_values[hash_text(matches[0])]['subgroup']]['sub_group_note']}</p>

			<p>For more information on this type of clause, see the page from <a href="{codex_url}">Contract Codex</a></p>
	</details>
	</div>
	'''
	
	def output_notmatch_as_html_string (sentence_being_reviewed, matches):
		return f'''<h3>{sentence_being_reviewed}</h3>
				<div class="noteBoxes type1">
					<details>
						<summary>Expand Notes</summary>
							{editor}
							{button}
					</details>
					<ul>
						<li>No sufficiently similar clauses were found in the database.</li>
						<li>Please review manually.</li>
					</ul>
				</div>
				'''
	
	style = """body { font-family: sans-serif; }
			#editor {
				border: 1px solid #ccc;
				padding: 10px;
				min-height: 20px;
				margin-bottom: 10px;
			}
			button {
				padding: 8px 15px;
				background-color: #007bff;
				color: white;
				border: none;
				cursor: pointer;
			}
			del { color: red; text-decoration: line-through; }
			ins { color: green; font-weight: bold; }
			.noteBoxes { border: 1px solid; border-radius: 5px; padding: 10px; margin: 10px 0; width: 90%; } .type1 { border-color: #E76F51; background-color: rgba(231, 111, 81, 0.1); } .type2 { border-color: #2A9D8F; background-color: rgba(42, 157, 143, 0.1); } .type3 { border-color: #0096C7; background-color: rgba(0, 150, 199, 0.1); } .type4 { border-color: #00B353; background-color: rgba(0, 179, 83, 0.1); } .picture { width: 15px; padding-right: 10px; }
			"""

	script = """
		function saveCurrentPage() {
			// Get the entire HTML content of the document
			const htmlContent = document.documentElement.outerHTML;
	
			// Create a Blob object from the HTML content
			const blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8' });
	
			// Create a URL for the Blob
			const url = URL.createObjectURL(blob);
	
			// Create a temporary anchor element
			const a = document.createElement('a');
			a.href = url;
			a.download = 'saved_page.html'; // Suggested filename for the download
			a.style.display = 'none'; // Hide the anchor element
	
			// Append the anchor to the body, click it, and then remove it
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
	
			// Revoke the object URL to free up resources
			URL.revokeObjectURL(url);
		}
	"""
	
	editor = """<div id="editor" contenteditable="true">
			Add your notes here...
			</div>"""
	button = """<button onclick="saveCurrentPage()">Save File</button>"""
	
	def process_contract(doc_text):
		html_string_result = ""
	
	
		for para in doc_text:
			# this should be matching paragraph
			if len(para.strip())==0:
				continue
	
			# Convert query sentence to embedding
			query_embedding = model.encode(para)
	
			## Find top 3 most similar sentences
			hits = semantic_search(query_embedding, sentence_embeddings, top_k=3)
			matches = []
	
			if hits[0][0]['score'] > cutoff_value:
	
				for idx, hit in enumerate(hits[0]):

					if hit['score'] >= cutoff_value:

						matches.append(f"{clause_phrases[hit['corpus_id']]}")



				if len(matches) > 0:
					html_string_result += output_results_as_html_string(para,matches)
			else:
				# if no matches found by paragraph then try breaking into sentences
				sentences = para.split('. ')
	
				for sentence in sentences:
					if len(sentence.strip())==0:
						continue
	
					query_embedding = model.encode(sentence)
					hits = semantic_search(query_embedding, sentence_embeddings, top_k=3)
					matches = []
	
					if hits[0][0]['score'] > secondary_cutoff_value:
	
						for idx, hit in enumerate(hits[0]):
	
							if hit['score'] >= secondary_cutoff_value:
	
								matches.append(f"{clause_phrases[hit['corpus_id']]}")
	
	
						if len(matches) > 0: #to verify something was matched. otherwise enter no match
							html_string_result += output_results_as_html_string(sentence,matches)
					else:
						html_string_result += output_notmatch_as_html_string(sentence,matches)# output_notmatch_as_md(para,matches)
	
		html_output = f"""<!DOCTYPE html>
		<html lang="en">
		<head>
			<meta charset="UTF-8">
			<meta name="viewport" content="width=device-width, initial-scale=1.0">
			<meta name="description" content="">
			<title>Contract Reference Tool</title>
			<style>
				{style}
			</style>
		</head>
		<body>
			<h1>Contract Reference Tool</h1>
			<p>{button}</p>
			<main>
				<div>
					{html_string_result}
				</div>
			</main>
			<p>{button}</p>
			<footer>
				<p>Powered by the <a href="https://www.contractcodex.com/">Contract Codex Community</a>.</p>
			</footer>
			<script>
				{script}
			</script>
		</body>
		</html>

		"""
		return html_output
	
	def build_custom_db_from_text(all_text):
		"""
		use this function to convert text of a custom clause codex. The result is a dictionary that can be added to the contract codex database for similarity search.
		The output dictionary will follow this pattern: {'main_group': {'maingroup_notes':'','sub_groups':{'sub_group_1_name':{'sub_group_note':'','sub_group_clauses':['a','b']}}}}
	
		The input text should be formated as follows:
			all_text = '''
						Main group: first k
	
						Main group notes: this is v and everything below
	
						Sub group: a
						Sub group notes: a1xxxxxx
						Sub group clause: a1axxxxxx
						Sub group clause: a1bxxxxxx
	
						Sub group: b
						Sub group notes: b1xxxxxx
						Sub group clause: b1axxxxxx
						Sub group clause: b1bxxxxxx
	
						Main group: second k
	
						Main group notes: this is v and everything below
	
						Sub group: 2a
						Sub group notes: 2a1xxxxxx
						Sub group clause: 2a1axxxxxx
						Sub group clause: 2a1bxxxxxx
	
						Sub group: 2b
						Sub group notes: 2b1xxxxxx
						Sub group clause: 2b1axxxxxx
						Sub group clause: 2b1bxxxxxx
						'''
	
		"""

		all_groups = process_text_to_dict_of_groups(all_text)

		hash_db_personal = pysos.Dict('pysos_hash_values_personal')
	
		data_db_personal = pysos.Dict('pysos_meta_data_db_personal')
	
		clauses_to_search = {}
		for k,v in all_groups.items():
			for a,b in v['sub_groups'].items():
	
				for c in b['sub_group_clauses']:
					clauses_to_search[c] = {'maingroup':k,'subgroup':a}
					for s in make_sentences_from_paragraph(c):
						if len(s)>0:
							clauses_to_search[s] = {'maingroup':k,'subgroup':a, 'larger_clause':c}
	
	
		data_db_personal = clauses_to_search

		for i,(k,v) in enumerate(clauses_to_search.items()):
	
			if 'larger_clause' in v:
				v['larger_clause'] = hash_text(v['larger_clause'])
			v |= {'clause':k}
	
	
			hash_db_personal[hash_text(k)] = v
	
		#hash_db |= hash_db_personal
		#data_db |= data_db_personal
		return hash_db_personal, data_db_personal



	#https://docs.flet.dev/services/filepicker/#pick-and-upload-files

	# Progress widgets (hidden until processing starts)
	progress_bar = ft.ProgressBar(width=400, visible=False)
	progress_percent = ft.Text("", visible=False)


	async def handle_pick_files(e: ft.Event[ft.Button]):
		files = await ft.FilePicker().pick_files(allow_multiple=False)
		if not files:
			return

		doc_text = get_text_from_file(files[0].path)

		# count non-empty paragraphs for progress
		total = sum(1 for p in doc_text if p.strip())
		if total == 0:
			return

		progress_bar.visible = True
		progress_percent.visible = True
		progress_bar.value = 0.0
		progress_percent.value = "0%"
		page.update()

		html_string_result = ""
		processed = 0

		for para in doc_text:
			if len(para.strip()) == 0:
				continue

			# Convert query sentence to embedding and search
			query_embedding = model.encode(para)
			hits = semantic_search(query_embedding, sentence_embeddings, top_k=3)
			matches = []

			if hits[0][0]['score'] > cutoff_value:
				for hit in hits[0]:
					if hit['score'] >= cutoff_value:
						matches.append(f"{clause_phrases[hit['corpus_id']]}")

				if len(matches) > 0:
					html_string_result += output_results_as_html_string(para, matches)
			else:
				sentences = para.split('. ')
				for sentence in sentences:
					if len(sentence.strip()) == 0:
						continue

					query_embedding = model.encode(sentence)
					hits = semantic_search(query_embedding, sentence_embeddings, top_k=3)
					matches = []

					if hits[0][0]['score'] > secondary_cutoff_value:
						for hit in hits[0]:
							if hit['score'] >= secondary_cutoff_value:
								matches.append(f"{clause_phrases[hit['corpus_id']]}")

						if len(matches) > 0:
							html_string_result += output_results_as_html_string(sentence, matches)
					else:
						html_string_result += output_notmatch_as_html_string(sentence, matches)

			processed += 1
			progress_bar.value = processed / total
			progress_percent.value = f"{int(progress_bar.value * 100)}%"
			page.update()
			await asyncio.sleep(0)
		
		# I asked vscode ai to add the progress bar to the function and it just replaced the code for the process contract function and added it here.
		html_output = f"""<!DOCTYPE html>
		<html lang="en">
		<head>
			<meta charset="UTF-8">
			<meta name="viewport" content="width=device-width, initial-scale=1.0">
			<meta name="description" content="">
			<title>Contract Reference Tool</title>
			<style>
				{style}
			</style>
		</head>
		<body>
			<h1>Contract Reference Tool</h1>
			<p>{button}</p>
			<main>
				<div>
					{html_string_result}
				</div>
			</main>
			<p>{button}</p>
			<footer>
				<p>Powered by the <a href="https://www.contractcodex.com/">Contract Codex Community</a>.</p>
			</footer>
			<script>
				{script}
			</script>
		</body>
		</html>

		"""
		with open(f'{files[0].path}.html', 'w') as f:
			f.write(html_output)
		# with open(f'src/assets/Reports/{files[0].name}.html', 'w') as f:
		# 	f.write(html_output)

		progress_bar.visible = False
		progress_percent.visible = False
		page.update()


	page.add(
		ft.Column(
			controls=[
				ft.Text("Contract Reference Tool"),
				ft.Text("Powered by Contract Codex"),
				ft.Row(
					controls=[
						ft.Button(
							content="Pick Contract File",
							icon=ft.Icons.UPLOAD_FILE,
							on_click=handle_pick_files,
						),
					]
				),
				ft.Row(controls=[progress_bar, progress_percent]),
			]
		)
	)
ft.run(main, assets_dir="assets")

if __name__ == "__main__":
    ft.run(main)
