// PantryPilot: every piece of on-screen text, in English and Spanish.
//
// HTML uses:   data-i18n="key"             -> sets the element's text
//              data-i18n-html="key"        -> sets text that contains simple markup WE wrote
//              data-i18n-attr="placeholder:key; aria-label:key"
// JavaScript:  t("key") or t("key", { name: "value" })  ("{name}" in the text gets replaced)
//
// Pantry names, addresses, and AI answers are data, not UI text, so they aren't translated here.
// To add a language: copy the "en" block, translate the values, and add a button in settings.js.

const STRINGS = {
  en: {
    // ----- shared -----
    "skip": "Skip to main content",
    "nav.label": "Main",
    "nav.map": "Map",
    "nav.ask": "Ask",
    "nav.hours": "Hours",
    "settings.group": "Display settings",
    "settings.lang": "Español",
    "settings.langLabel": "Cambiar a español",
    "settings.large": "Larger text",
    "settings.contrast": "High contrast",
    "time.am": "AM",
    "time.pm": "PM",
    "and": "&",

    // ----- map page -----
    "map.pageTitle": "PantryPilot",
    "map.tagline": "Free food near you in Collin & Denton County",
    "map.zipLabel": "ZIP code",
    "map.zipPlaceholder": "ZIP code",
    "map.search": "Search",
    "map.nearMe": "Near me",
    "map.filters": "Filters",
    "filter.open_now": "Open now",
    "filter.no_id": "No ID needed",
    "filter.drive_thru": "Drive-thru",
    "filter.spanish": "Spanish spoken",
    "map.region": "Map of food pantries",
    "map.keyboardHint": "The same pantries are in the list below. Use the list to choose one with a keyboard or screen reader.",
    "map.legend": "Map legend",
    "map.zoomIn": "Zoom in",
    "map.zoomOut": "Zoom out",
    "map.youAreHere": "You are here",
    "legend.open": "Open",
    "legend.later_today": "Later today",
    "legend.appointment": "Appointment",
    "legend.closed": "Closed",
    "legend.unknown": "Call for hours",
    "status.open": "Open now",
    "status.later_today": "Opens later today",
    "status.appointment": "Appointment needed",
    "status.closed": "Closed now",
    "status.unknown": "Call for hours",
    "status.offline": "Status needs internet",
    "list.title": "Pantries",
    "list.nearest": "Nearest pantries",
    "list.count": "({n})",
    "list.empty": "No pantries match these filters. Try turning one off.",
    "list.notOnMap": "not on map",
    "list.miles": "{n} mi",
    "details.close": "Close details",
    "details.noAddress": "Address not listed",
    "details.away": " · {n} mi away",
    "details.hours": "Hours",
    "details.know": "What to know",
    "details.idYes": "ID required",
    "details.idNo": "No ID needed",
    "details.idUnknown": "ID: not listed, so bring one if you can",
    "details.serves": "Serves: {who}",
    "details.driveThru": "Drive-thru available",
    "details.spanish": "Se habla español",
    "details.call": "Call {phone}",
    "details.directions": "Get directions",
    "details.verified": "Last verified: {date}",
    "details.notVerified": "Not yet verified",
    "details.listedAs": "Listed as: \"{text}\"",
    "hours.always": "Open 24 hours, every day",
    "hours.apptOnly": "By appointment only. Call to schedule.",
    "hours.unknown": "Hours not confirmed. Please call first.",
    "hours.alsoAppt": "Other times by appointment",
    "hours.apptTag": " (appointment)",
    "day.mon": "Mon", "day.tue": "Tue", "day.wed": "Wed", "day.thu": "Thu",
    "day.fri": "Fri", "day.sat": "Sat", "day.sun": "Sun",
    "week.1": "1st", "week.2": "2nd", "week.3": "3rd", "week.4": "4th", "week.5": "5th", "week.last": "Last",
    "month.1": "Jan", "month.2": "Feb", "month.3": "Mar", "month.4": "Apr", "month.5": "May", "month.6": "Jun",
    "month.7": "Jul", "month.8": "Aug", "month.9": "Sep", "month.10": "Oct", "month.11": "Nov", "month.12": "Dec",
    "msg.zipInvalid": "Please enter a 5-digit ZIP code, like 75034.",
    "msg.zipNotFound": "ZIP code {zip} isn't in our Collin/Denton County list.",
    "msg.badInput": "Please check what you typed.",
    "msg.network": "Couldn't reach PantryPilot. Check your internet connection and try again.",
    "msg.noGeo": "Your browser can't share your location. Try a ZIP code instead.",
    "msg.finding": "Finding your location…",
    "msg.geoFailed": "Couldn't get your location. Try a ZIP code instead.",
    "msg.offline": "You're offline. Showing the pantry list saved {when}. Open/closed status needs internet, so check each pantry's hours.",
    "msg.openNowOffline": "\"Open now\" needs internet.",
    "msg.zipOffline": "ZIP search needs internet.",
    "map.footnote": "Hours change. Please call ahead when you can. Map data © <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors.",

    // ----- hours page -----
    "hrs.pageTitle": "Hours Coach · PantryPilot",
    "hrs.title": "Hours Coach",
    "hrs.tagline": "Track work, volunteer, and training hours toward 80 a month",
    "hrs.privacy": "<strong>Your hours stay on your phone.</strong> Your entries are saved only in this browser, and there's no account. To estimate your chances, only anonymous weekly totals are sent (no dates, names, or entries), and nothing is saved.",
    "hrs.storageWarning": "This browser won't let PantryPilot save data (private browsing can do this). Hours you add will disappear when you close the page.",
    "hrs.progressTitle": "This month's progress",
    "hrs.ofGoal": "of 80 hours this month",
    "hrs.toGo": "{hours} hours to go",
    "hrs.daysLeft": " · {n} {dayWord} left in {month} (including today)",
    "hrs.reached": "You've logged 80 hours for {month}!",
    "hrs.reachedDays": " {n} {dayWord} left in the month.",
    "hrs.day": "day",
    "hrs.days": "days",
    "hrs.forecastTitle": "Your chances this month",
    "hrs.forecastLoading": "Working out your chances…",
    "hrs.forecastError": "Couldn't work out your chances right now. Your hours are still saved.",
    "hrs.chanceMore": "More than 9 in 10",
    "hrs.chanceLess": "Less than 1 in 10",
    "hrs.chanceAbout": "About {n} in 10",
    "hrs.chanceSuffix": "chance you'll reach 80 hours this month",
    "hrs.alreadyReached": "You've already reached 80 hours this month!",
    "hrs.rangeAbout": "You'll likely end with about {n} hours.",
    "hrs.range": "You'll likely end between {low} and {high} hours.",
    "hrs.basisMany": "Based on your last {n} weeks of hours.",
    "hrs.basisNone": "Based on a typical week, since you haven't logged a full week yet. It gets more personal as you log more.",
    "hrs.basisFew": "Based on your {n} {weekWord} of hours mixed with a typical week, until you've logged 3 weeks.",
    "hrs.week": "week",
    "hrs.weeks": "weeks",
    "hrs.whatIfButton": "What if I add a 4-hour volunteer shift?",
    "hrs.whatIfSame": "With one more {h}-hour shift: still {before}. Every hour still counts toward 80.",
    "hrs.whatIfUp": "With one more {h}-hour shift: {after} (up from {before}).",
    "hrs.waysTitle": "Ways to add hours",
    "hrs.waysShift": "{n}-hour shifts",
    "hrs.waysPantry": "Ask at a food pantry near you",
    "hrs.waysPantryText": "Many pantries on the map need volunteers. Call and ask about shifts.",
    "hrs.forecastNote": "An estimate from 10,000 simulations of your past weeks, not a guarantee.",
    "hrs.addTitle": "Add hours",
    "hrs.date": "Date",
    "hrs.hours": "Hours",
    "hrs.hoursPlaceholder": "e.g. 4",
    "hrs.type": "Type",
    "type.work": "Work",
    "type.volunteer": "Volunteer",
    "type.training": "Job training",
    "hrs.addButton": "Add hours",
    "hrs.errDate": "Pick a date.",
    "hrs.errFuture": "You can't log hours for a future date.",
    "hrs.errHours": "Enter how many hours, like 4 or 2.5.",
    "hrs.errTooMany": "A day only has 24 hours. Please check the number.",
    "hrs.otherMonth": "Saved. That date isn't in this month, so it won't count toward this month's 80.",
    "hrs.weeksTitle": "Hours by week",
    "hrs.thisWeek": " (this week)",
    "hrs.hoursShort": "{n} h",
    "hrs.paceKey": "20 hours a week keeps you on track for 80",
    "hrs.entriesTitle": "This month's entries",
    "hrs.noEntries": "No hours yet this month. Add your first entry above.",
    "hrs.delete": "Delete {hours} hours of {type} on {day}",
    "hrs.deleted": "Deleted {hours} h ({type}).",
    "hrs.undo": "Undo",
    "hrs.download": "Download my monthly summary",
    "hrs.footnote": "This is a personal tracker, not an official SNAP record, and it can't tell you whether you meet a work requirement. Keep your own proof (pay stubs, sign-in sheets) and check with Texas HHS or your caseworker.",
    "pdf.making": "Making your PDF…",
    "pdf.done": "Your summary was downloaded.",
    "pdf.failed": "Couldn't make the PDF. Check your internet connection and try again.",
    "pdf.title": "Monthly Hours Summary: {month} {year}",
    "pdf.created": "Created {date}",
    "pdf.name": "Name: ______________________________",
    "pdf.total": "Total: {hours} of 80 hours",
    "pdf.entryOne": "{n} entry",
    "pdf.entryMany": "{n} entries",
    "pdf.entries": "Entries",
    "pdf.byDay": "Hours by day",
    "pdf.colDate": "Date",
    "pdf.colType": "Type",
    "pdf.colHours": "Hours",
    "pdf.none": "No hours logged this month.",
    "pdf.totalRow": "Total",
    "pdf.proof": "Hours are entered by the user. Keep your own proof, such as pay stubs or sign-in sheets.",

    // ----- ask page -----
    "ask.pageTitle": "Ask · PantryPilot",
    "ask.title": "Ask PantryPilot",
    "ask.tagline": "Food help questions in English or Spanish",
    "ask.intro": "<strong>I answer only from trusted sources</strong> and show you where each answer came from. I can't tell you if you qualify for a program. For that, contact <a href=\"https://www.yourtexasbenefits.com\" target=\"_blank\" rel=\"noopener\">Texas HHSC</a> or dial <strong>2-1-1</strong>.",
    "ask.tryAsking": "Try asking",
    "ask.conversation": "Conversation",
    "ask.questionLabel": "Your question",
    "ask.placeholder": "Ask a question",
    "ask.send": "Send question",
    "ask.note": "Please don't type your name, case number, or SSN.",
    "ask.thinking": "Looking through trusted sources…",
    "ask.sources": "Sources",
    "ask.errGeneric": "Something went wrong. Please try again, or dial 2-1-1.",
    "ask.errNetwork": "Couldn't connect. Check your internet, or dial 2-1-1.",
    "ask.errTooMany": "You've asked a lot of questions. Please wait a few minutes, or dial 2-1-1.",
    "ask.errUnavailable": "The assistant isn't available right now. Please dial 2-1-1 for help.",
    "ask.offline": "You're offline. The assistant needs internet, but you can always call 2-1-1.",
    "ask.cite": "Source {n}: {title}",
    "ask.howFound": "How I found this",
    "ask.foundOfficial": "Checked official sources: {list}",
    "ask.foundPantries": "Checked {n} pantries with live open/closed status",
    "ask.foundFilter": "Only pantries marked: {list}",
    "ask.foundPlanned": "Searched official sources for: {list}",
    "ask.foundNothing": "No official source matched, so I didn't answer from memory.",
    "ask.call": "Call",
    "ask.directions": "Directions",
    "ask.suggestions": "You could also ask",
    "ask.voice": "Speak your question",
    "ask.voiceStop": "Stop listening",
    "ask.voiceNote": "Voice typing uses your browser's speech service. Check the words before you send.",
    "ask.listen": "Listen",
    "ask.stopListening": "Stop reading",
  },

  es: {
    // ----- shared -----
    "skip": "Saltar al contenido principal",
    "nav.label": "Principal",
    "nav.map": "Mapa",
    "nav.ask": "Preguntar",
    "nav.hours": "Horas",
    "settings.group": "Opciones de pantalla",
    "settings.lang": "English",
    "settings.langLabel": "Switch to English",
    "settings.large": "Letra más grande",
    "settings.contrast": "Alto contraste",
    "time.am": "a. m.",
    "time.pm": "p. m.",
    "and": "y",

    // ----- map page -----
    "map.pageTitle": "PantryPilot",
    "map.tagline": "Comida gratis cerca de usted en los condados de Collin y Denton",
    "map.zipLabel": "Código postal",
    "map.zipPlaceholder": "Código postal",
    "map.search": "Buscar",
    "map.nearMe": "Cerca de mí",
    "map.filters": "Filtros",
    "filter.open_now": "Abierto ahora",
    "filter.no_id": "Sin identificación",
    "filter.drive_thru": "Desde el auto",
    "filter.spanish": "Se habla español",
    "map.region": "Mapa de despensas de comida",
    "map.keyboardHint": "Las mismas despensas están en la lista de abajo. Use la lista para elegir una con el teclado o un lector de pantalla.",
    "map.legend": "Leyenda del mapa",
    "map.zoomIn": "Acercar",
    "map.zoomOut": "Alejar",
    "map.youAreHere": "Usted está aquí",
    "legend.open": "Abierto",
    "legend.later_today": "Más tarde hoy",
    "legend.appointment": "Con cita",
    "legend.closed": "Cerrado",
    "legend.unknown": "Llame para horario",
    "status.open": "Abierto ahora",
    "status.later_today": "Abre más tarde hoy",
    "status.appointment": "Se necesita cita",
    "status.closed": "Cerrado ahora",
    "status.unknown": "Llame para confirmar horario",
    "status.offline": "El estado requiere internet",
    "list.title": "Despensas",
    "list.nearest": "Despensas más cercanas",
    "list.count": "({n})",
    "list.empty": "Ninguna despensa coincide con estos filtros. Pruebe quitando uno.",
    "list.notOnMap": "no está en el mapa",
    "list.miles": "{n} mi",
    "details.close": "Cerrar detalles",
    "details.noAddress": "Dirección no disponible",
    "details.away": " · a {n} mi",
    "details.hours": "Horario",
    "details.know": "Información útil",
    "details.idYes": "Se requiere identificación",
    "details.idNo": "No se necesita identificación",
    "details.idUnknown": "Identificación: no indicado; tráigala si puede",
    "details.serves": "Atiende a: {who}",
    "details.driveThru": "Servicio desde el auto",
    "details.spanish": "Se habla español",
    "details.call": "Llamar al {phone}",
    "details.directions": "Cómo llegar",
    "details.verified": "Última verificación: {date}",
    "details.notVerified": "Aún no verificado",
    "details.listedAs": "Según la lista: \"{text}\"",
    "hours.always": "Abierto las 24 horas, todos los días",
    "hours.apptOnly": "Solo con cita. Llame para hacer una cita.",
    "hours.unknown": "Horario no confirmado. Llame antes de ir.",
    "hours.alsoAppt": "Otros horarios con cita",
    "hours.apptTag": " (con cita)",
    "day.mon": "lun", "day.tue": "mar", "day.wed": "mié", "day.thu": "jue",
    "day.fri": "vie", "day.sat": "sáb", "day.sun": "dom",
    "week.1": "1.er", "week.2": "2.º", "week.3": "3.er", "week.4": "4.º", "week.5": "5.º", "week.last": "Último",
    "month.1": "ene", "month.2": "feb", "month.3": "mar", "month.4": "abr", "month.5": "may", "month.6": "jun",
    "month.7": "jul", "month.8": "ago", "month.9": "sep", "month.10": "oct", "month.11": "nov", "month.12": "dic",
    "msg.zipInvalid": "Escriba un código postal de 5 dígitos, como 75034.",
    "msg.zipNotFound": "El código postal {zip} no está en nuestra lista de los condados de Collin y Denton.",
    "msg.badInput": "Revise lo que escribió.",
    "msg.network": "No se pudo conectar con PantryPilot. Revise su conexión a internet e intente de nuevo.",
    "msg.noGeo": "Su navegador no puede compartir su ubicación. Pruebe con un código postal.",
    "msg.finding": "Buscando su ubicación…",
    "msg.geoFailed": "No se pudo obtener su ubicación. Pruebe con un código postal.",
    "msg.offline": "Está sin conexión. Mostrando la lista de despensas guardada {when}. Para saber si están abiertas se necesita internet; revise el horario de cada despensa.",
    "msg.openNowOffline": "\"Abierto ahora\" necesita internet.",
    "msg.zipOffline": "La búsqueda por código postal necesita internet.",
    "map.footnote": "Los horarios cambian. Llame antes cuando pueda. Datos del mapa © colaboradores de <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a>.",

    // ----- hours page -----
    "hrs.pageTitle": "Asistente de horas · PantryPilot",
    "hrs.title": "Asistente de horas",
    "hrs.tagline": "Registre horas de trabajo, voluntariado y capacitación para llegar a 80 al mes",
    "hrs.privacy": "<strong>Sus horas se quedan en su teléfono.</strong> Sus registros se guardan solo en este navegador y no hay cuenta. Para calcular sus probabilidades, solo se envían totales semanales anónimos (sin fechas, nombres ni registros) y no se guarda nada.",
    "hrs.storageWarning": "Este navegador no permite que PantryPilot guarde datos (la navegación privada puede causar esto). Las horas que agregue se borrarán al cerrar la página.",
    "hrs.progressTitle": "Progreso de este mes",
    "hrs.ofGoal": "de 80 horas este mes",
    "hrs.toGo": "Faltan {hours} horas",
    "hrs.daysLeft": " · quedan {n} {dayWord} en {month} (contando hoy)",
    "hrs.reached": "¡Registró 80 horas en {month}!",
    "hrs.reachedDays": " Quedan {n} {dayWord} en el mes.",
    "hrs.day": "día",
    "hrs.days": "días",
    "hrs.forecastTitle": "Sus probabilidades este mes",
    "hrs.forecastLoading": "Calculando sus probabilidades…",
    "hrs.forecastError": "No se pudieron calcular sus probabilidades ahora. Sus horas siguen guardadas.",
    "hrs.chanceMore": "Más de 9 de 10",
    "hrs.chanceLess": "Menos de 1 de 10",
    "hrs.chanceAbout": "Aproximadamente {n} de 10",
    "hrs.chanceSuffix": "probabilidades de llegar a 80 horas este mes",
    "hrs.alreadyReached": "¡Ya llegó a 80 horas este mes!",
    "hrs.rangeAbout": "Probablemente terminará con unas {n} horas.",
    "hrs.range": "Probablemente terminará con entre {low} y {high} horas.",
    "hrs.basisMany": "Basado en sus últimas {n} semanas de horas.",
    "hrs.basisNone": "Basado en una semana típica, porque aún no ha registrado una semana completa. Será más personal a medida que registre más.",
    "hrs.basisFew": "Basado en sus {n} {weekWord} de horas combinadas con una semana típica, hasta que registre 3 semanas.",
    "hrs.week": "semana",
    "hrs.weeks": "semanas",
    "hrs.whatIfButton": "¿Y si agrego un turno de voluntariado de 4 horas?",
    "hrs.whatIfSame": "Con un turno más de {h} horas: sigue en {before}. Cada hora cuenta para llegar a 80.",
    "hrs.whatIfUp": "Con un turno más de {h} horas: {after} (antes {before}).",
    "hrs.waysTitle": "Maneras de sumar horas",
    "hrs.waysShift": "turnos de {n} horas",
    "hrs.waysPantry": "Pregunte en una despensa cerca de usted",
    "hrs.waysPantryText": "Muchas despensas del mapa necesitan voluntarios. Llame y pregunte por los turnos.",
    "hrs.forecastNote": "Un cálculo basado en 10,000 simulaciones de sus semanas pasadas, no una garantía.",
    "hrs.addTitle": "Agregar horas",
    "hrs.date": "Fecha",
    "hrs.hours": "Horas",
    "hrs.hoursPlaceholder": "ej. 4",
    "hrs.type": "Tipo",
    "type.work": "Trabajo",
    "type.volunteer": "Voluntariado",
    "type.training": "Capacitación laboral",
    "hrs.addButton": "Agregar horas",
    "hrs.errDate": "Elija una fecha.",
    "hrs.errFuture": "No puede registrar horas en una fecha futura.",
    "hrs.errHours": "Escriba cuántas horas, como 4 o 2.5.",
    "hrs.errTooMany": "Un día solo tiene 24 horas. Revise el número.",
    "hrs.otherMonth": "Guardado. Esa fecha no es de este mes, así que no cuenta para las 80 de este mes.",
    "hrs.weeksTitle": "Horas por semana",
    "hrs.thisWeek": " (esta semana)",
    "hrs.hoursShort": "{n} h",
    "hrs.paceKey": "20 horas por semana lo mantienen en camino a 80",
    "hrs.entriesTitle": "Registros de este mes",
    "hrs.noEntries": "Aún no hay horas este mes. Agregue su primer registro arriba.",
    "hrs.delete": "Eliminar {hours} horas de {type} del {day}",
    "hrs.deleted": "Se eliminaron {hours} h ({type}).",
    "hrs.undo": "Deshacer",
    "hrs.download": "Descargar mi resumen mensual",
    "hrs.footnote": "Este es un registro personal, no un registro oficial de SNAP, y no puede decirle si cumple con un requisito de trabajo. Guarde sus comprobantes (talones de pago, hojas de asistencia) y consulte con Texas HHS o su trabajador de caso.",
    "pdf.making": "Creando su PDF…",
    "pdf.done": "Se descargó su resumen.",
    "pdf.failed": "No se pudo crear el PDF. Revise su conexión a internet e intente de nuevo.",
    "pdf.title": "Resumen mensual de horas: {month} {year}",
    "pdf.created": "Creado el {date}",
    "pdf.name": "Nombre: ______________________________",
    "pdf.total": "Total: {hours} de 80 horas",
    "pdf.entryOne": "{n} registro",
    "pdf.entryMany": "{n} registros",
    "pdf.entries": "Registros",
    "pdf.byDay": "Horas por día",
    "pdf.colDate": "Fecha",
    "pdf.colType": "Tipo",
    "pdf.colHours": "Horas",
    "pdf.none": "No hay horas registradas este mes.",
    "pdf.totalRow": "Total",
    "pdf.proof": "Las horas las anota el usuario. Guarde sus comprobantes, como talones de pago u hojas de asistencia.",

    // ----- ask page -----
    "ask.pageTitle": "Preguntar · PantryPilot",
    "ask.title": "Pregúntele a PantryPilot",
    "ask.tagline": "Preguntas sobre ayuda con comida, en español o inglés",
    "ask.intro": "<strong>Respondo solo con fuentes confiables</strong> y le muestro de dónde viene cada respuesta. No puedo decirle si califica para un programa. Para eso, comuníquese con <a href=\"https://www.yourtexasbenefits.com\" target=\"_blank\" rel=\"noopener\">Texas HHSC</a> o llame al <strong>2-1-1</strong>.",
    "ask.tryAsking": "Pruebe preguntar",
    "ask.conversation": "Conversación",
    "ask.questionLabel": "Su pregunta",
    "ask.placeholder": "Escriba su pregunta",
    "ask.send": "Enviar pregunta",
    "ask.note": "No escriba su nombre, número de caso ni número de Seguro Social.",
    "ask.thinking": "Buscando en fuentes confiables…",
    "ask.sources": "Fuentes",
    "ask.errGeneric": "Algo salió mal. Intente de nuevo o llame al 2-1-1.",
    "ask.errNetwork": "No hay conexión. Revise su internet o llame al 2-1-1.",
    "ask.errTooMany": "Ha hecho muchas preguntas. Espere unos minutos o llame al 2-1-1.",
    "ask.errUnavailable": "El asistente no está disponible ahora. Llame al 2-1-1 para recibir ayuda.",
    "ask.offline": "Está sin conexión. El asistente necesita internet, pero siempre puede llamar al 2-1-1.",
    "ask.cite": "Fuente {n}: {title}",
    "ask.howFound": "Cómo encontré esto",
    "ask.foundOfficial": "Fuentes oficiales revisadas: {list}",
    "ask.foundPantries": "Se revisaron {n} despensas con su estado actual (abierta/cerrada)",
    "ask.foundFilter": "Solo despensas marcadas: {list}",
    "ask.foundPlanned": "Búsqueda en fuentes oficiales: {list}",
    "ask.foundNothing": "Ninguna fuente oficial coincidió, así que no respondí de memoria.",
    "ask.call": "Llamar",
    "ask.directions": "Cómo llegar",
    "ask.suggestions": "También puede preguntar",
    "ask.voice": "Diga su pregunta",
    "ask.voiceStop": "Dejar de escuchar",
    "ask.voiceNote": "El dictado por voz usa el servicio de voz de su navegador. Revise las palabras antes de enviar.",
    "ask.listen": "Escuchar",
    "ask.stopListening": "Dejar de leer",
  },
};

// Starter questions on the Ask page. The current language's questions are shown first.
const STARTER_QUESTIONS = {
  en: [
    "How do I apply for SNAP in Texas?",
    "What does WIC give families?",
    "Which food pantries in Plano are open today?",
  ],
  es: [
    "¿Cómo solicito los beneficios de SNAP?",
    "¿Qué es WIC y quién puede recibirlo?",
    "¿Qué despensas de comida hay en McKinney?",
  ],
};

// Follow-up questions shown under answers. Each one is answerable from PantryPilot's own
// sources (the official pages in knowledge/ or the pantry list), so a suggestion never leads
// to "not sure". Grouped by what the answer was based on.
const SUGGESTED_QUESTIONS = {
  en: {
    snap: ["What can I buy with SNAP?", "What are the SNAP work rules?", "How much SNAP can a family get?"],
    wic: ["How do I apply for WIC?", "What does WIC give families?", "What happens at the first WIC appointment?"],
    two11: ["Which food pantries are open today?", "How do I apply for SNAP in Texas?"],
    pantry: ["Which pantries are open right now?", "Which pantries don't require ID?", "Which pantries have drive-thru?"],
    general: ["Which food pantries are open today?", "How do I apply for SNAP in Texas?", "What does WIC give families?"],
  },
  es: {
    snap: ["¿Qué puedo comprar con SNAP?", "¿Cuáles son las reglas de trabajo de SNAP?", "¿Cuánto SNAP puede recibir una familia?"],
    wic: ["¿Cómo solicito WIC?", "¿Qué es WIC y quién puede recibirlo?", "¿Qué pasa en la primera cita de WIC?"],
    two11: ["¿Qué despensas de comida están abiertas hoy?", "¿Cómo solicito SNAP en Texas?"],
    pantry: ["¿Qué despensas están abiertas ahora?", "¿Qué despensas no piden identificación?", "¿Qué despensas tienen servicio desde el auto?"],
    general: ["¿Qué despensas de comida están abiertas hoy?", "¿Cómo solicito SNAP en Texas?", "¿Qué es WIC y quién puede recibirlo?"],
  },
};

// ---------- saving choices (works even when storage is blocked) ----------

function storageGet(key) {
  try { return localStorage.getItem(key); } catch (error) { return null; }
}

function storageSet(key, value) {
  try { localStorage.setItem(key, value); } catch (error) { /* private mode: just don't remember */ }
}

// ---------- the current language ----------

const LANG_KEY = "pantrypilot.lang";

let currentLang = (() => {
  const saved = storageGet(LANG_KEY);
  if (saved === "en" || saved === "es") return saved;
  // First visit: follow the phone's language.
  return (navigator.language || "").toLowerCase().startsWith("es") ? "es" : "en";
})();
document.documentElement.lang = currentLang;

function getLang() {
  return currentLang;
}

// For dates and numbers: "Sep 28" vs "28 sept".
function locale() {
  return currentLang === "es" ? "es-US" : "en-US";
}

function t(key, vars = {}) {
  let text = STRINGS[currentLang][key];
  if (text === undefined) text = STRINGS.en[key];
  if (text === undefined) {
    console.warn(`Missing text for "${key}"`);
    return key;
  }
  return text.replace(/\{(\w+)\}/g, (match, name) => (name in vars ? String(vars[name]) : match));
}

// Fill in every marked element on the page.
function applyTranslations(root = document) {
  for (const node of root.querySelectorAll("[data-i18n]")) {
    node.textContent = t(node.dataset.i18n);
  }
  // Only OUR strings above go through innerHTML, never user input or AI answers.
  for (const node of root.querySelectorAll("[data-i18n-html]")) {
    node.innerHTML = t(node.dataset.i18nHtml);
  }
  for (const node of root.querySelectorAll("[data-i18n-attr]")) {
    for (const pair of node.dataset.i18nAttr.split(";")) {
      const [attr, key] = pair.split(":").map((part) => part.trim());
      if (attr && key) node.setAttribute(attr, t(key));
    }
  }
}

function setLang(lang) {
  currentLang = lang;
  storageSet(LANG_KEY, lang);
  document.documentElement.lang = lang;
  applyTranslations();
  // Each page listens for this and redraws the text it builds in JavaScript.
  document.dispatchEvent(new CustomEvent("pp:languagechange"));
}
