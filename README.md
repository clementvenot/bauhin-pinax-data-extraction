# 📘 Guide d’utilisation
**Caspar Bauhin – Extraction de données**

---

## 1. 🎯 Objectif

Cette application a pour objectif de faciliter l’extraction, la structuration et l’export des taxons issus du *Pinax* de Gaspard Bauhin à partir de documents PDF.

---

## 2. 🚀 Démarrage

1. Lancez l’exécutable  
2. Cliquez sur **Ouvrir PDF**  
3. Sélectionnez le document à analyser (PDF du *Pinax* de Gaspard Bauhin)  
4. Patientez pendant le chargement de la première page  

### Navigation dans le document

Le déplacement entre les pages peut se faire grâce à :

- les boutons **`<`** et **`>`**  
- le champ **Aller à la page**  

---

## 3. 🧩 Définition des zones

Les zones des pages sont détectées automatiquement. Toutefois, des erreurs peuvent apparaître en raison de la qualité ou de l’ancienneté du document.

L’utilisateur peut alors :

- supprimer des zones  
- déplacer des zones  
- ajouter de nouvelles zones  
- modifier le type des zones  

### Procédure

1. Sélectionner un type  
2. Cliquer sur **Ajouter un rectangle**  
3. Dessiner la zone sur l’image  
4. Ajuster la zone si nécessaire :
   - déplacement  
   - redimensionnement  
   - suppression  

---

## 4. ✅ Validation d’une page

Lorsque les zones sont définies :

1. Cliquer sur **Valider bordure page**  
2. Une fenêtre de correction OCR apparaît  
3. Vérifier les données extraites  
4. Corriger si nécessaire  
5. Cliquer sur **Valider**  

### ⚠️ Points importants

- Les pages doivent être validées dans l’ordre  
- La première page nécessite au moins un rectangle de type **genre**  
- La validation suit un flux séquentiel strict  

---

## 5. 📊 Panneau de droite

Le panneau de droite contient deux sections :

### 🌿 Genres validés

Pour chaque genre :

- affichage dans une liste  
- clic = ouverture du détail  

Dans le détail :

- le genre apparaît en premier  
- les taxons sont listés ensuite  
- les références sont affichées sous les taxons  
- les variétés restent associées aux taxons correspondants  

---

### ✍️ Textes italiques

Chaque entrée contient :

- une miniature de la zone  
- le texte extrait  
- la localisation détectée (si disponible)  

---

## 6. 📚 Gestion des références

Avant l’export, l’application peut demander un fichier Excel de références.

### Format attendu

- Colonne 1 : **id**  
- Colonne 2 : **reference**  
- La première ligne est ignorée  

### Fonctionnement

- Le fichier est chargé une seule fois par session  
- Il peut être modifié et rechargé lors d’une nouvelle session  

---

## 7. 📤 Export Excel

Une fois les références chargées, le bouton devient **Exporter Excel**.

### Étapes

1. Choisir l’emplacement du fichier `.xlsx`  

### Traitement des références

- L’application remplace les correspondances par leur **id**  
- Le texte non reconnu est conservé  

### Contenu du fichier Excel

- Feuille **Genres validés**  
- Feuille **Textes italiques**  

---

## 8. 💡 Bonnes pratiques

- ✅ Valider uniquement lorsque la page est prête  
- ✅ Toujours relire les corrections OCR  
- ✅ Vérifier les références non reconnues  

---

## 9. 🔄 Flux recommandé

Ouvrir le PDF → Définir les zones → Valider la page → Corriger l’OCR → Confirmer la validation → Passer à la page suivante → Répéter → Charger les références si nécessaire → Exporter les données en Excel  
