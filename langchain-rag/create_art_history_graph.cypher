MATCH (n) DETACH DELETE n;

CREATE (:Artist {name: 'Leonardo da Vinci', birth_year: 1452, death_year: 1519, nationality: 'Italian', biography: 'Renaissance polymath, painter, scientist, engineer', gender: 'Male', art_movements: ['Renaissance', 'High Renaissance'], notable_works: ['Mona Lisa', 'The Last Supper', 'Vitruvian Man'], techniques_used: ['Sfumato', 'Chiaroscuro', 'Oil painting']});

CREATE (:Artist {name: 'Michelangelo Buonarroti', birth_year: 1475, death_year: 1564, nationality: 'Italian', biography: 'Renaissance sculptor, painter, architect, poet', gender: 'Male', art_movements: ['Renaissance', 'High Renaissance'], notable_works: ['David', 'Pieta', 'Sistine Chapel Ceiling'], techniques_used: ['Marble sculpture', 'Fresco painting']});

CREATE (:Artist {name: 'Claude Monet', birth_year: 1840, death_year: 1926, nationality: 'French', biography: 'Founder of French Impressionist painting', gender: 'Male', art_movements: ['Impressionism'], notable_works: ['Water Lilies', 'Impression, Sunrise', 'Rouen Cathedral'], techniques_used: ['Plein air painting', 'Broken color']});

CREATE (:Artist {name: 'Vincent van Gogh', birth_year: 1853, death_year: 1890, nationality: 'Dutch', biography: 'Post-Impressionist painter known for emotional directness', gender: 'Male', art_movements: ['Post-Impressionism'], notable_works: ['The Starry Night', 'Sunflowers', 'The Bedroom'], techniques_used: ['Impasto', 'Expressive brushwork']});

CREATE (:Artist {name: 'Pablo Picasso', birth_year: 1881, death_year: 1973, nationality: 'Spanish', biography: 'Co-founder of Cubism, prolific artist across multiple periods', gender: 'Male', art_movements: ['Cubism', 'Blue Period', 'Rose Period'], notable_works: ["Les Demoiselles d'Avignon", 'Guernica', 'Girl Before a Mirror'], techniques_used: ['Cubist fragmentation', 'Mixed media']});

CREATE (:Artwork {title: 'Mona Lisa', creation_date: 1503, artist: 'Leonardo da Vinci', description: 'Portrait of Lisa Gherardini with enigmatic smile', dimensions: '77 cm × 53 cm', medium: 'Oil on poplar panel', technique: 'Sfumato', significance: 'Most famous painting in the world', theme: ['Portrait', 'Renaissance humanism'], style: 'High Renaissance'});

CREATE (:Artwork {title: 'The Last Supper', creation_date: 1495, artist: 'Leonardo da Vinci', description: 'Depiction of Jesus announcing betrayal to disciples', dimensions: '460 cm × 880 cm', medium: 'Tempera and oil on dry wall', technique: 'Linear perspective', significance: 'Masterpiece of composition and emotion', theme: ['Religious', 'Biblical'], style: 'High Renaissance'});

CREATE (:Artwork {title: 'David', creation_date: 1504, artist: 'Michelangelo Buonarroti', description: 'Biblical hero David before battle with Goliath', dimensions: '517 cm height', medium: 'Carrara marble', technique: 'Marble sculpture', significance: 'Symbol of the Republic of Florence', theme: ['Biblical', 'Heroic'], style: 'High Renaissance'});

CREATE (:Artwork {title: 'Water Lilies', creation_date: 1919, artist: 'Claude Monet', description: 'Series of water lily pond paintings', dimensions: 'Various sizes', medium: 'Oil on canvas', technique: 'Impressionist brushwork', significance: 'Pinnacle of Impressionist landscape', theme: ['Nature', 'Light', 'Reflection'], style: 'Impressionism'});

CREATE (:Artwork {title: 'The Starry Night', creation_date: 1889, artist: 'Vincent van Gogh', description: 'Night sky over a village with swirling clouds', dimensions: '73.7 cm × 92.1 cm', medium: 'Oil on canvas', technique: 'Impasto', significance: 'Icon of modern art', theme: ['Night', 'Village', 'Cosmic'], style: 'Post-Impressionism'});

CREATE (:Movement {name: 'Renaissance', start_period: 1400, end_period: 1600, origin_location: 'Italy', characteristics: 'Revival of classical learning, humanism, perspective', key_principles: ['Humanism', 'Linear perspective', 'Classical mythology'], major_figures: ['Leonardo da Vinci', 'Michelangelo', 'Raphael'], historical_context: 'Transition from Medieval to Early Modern Europe'});

CREATE (:Movement {name: 'Impressionism', start_period: 1860, end_period: 1886, origin_location: 'France', characteristics: 'Capturing light and momentary effects', key_principles: ['Plein air painting', 'Broken color', 'Light effects'], major_figures: ['Claude Monet', 'Pierre-Auguste Renoir', 'Edgar Degas'], historical_context: 'Industrial revolution and modern urban life'});

CREATE (:Movement {name: 'Post-Impressionism', start_period: 1880, end_period: 1905, origin_location: 'France', characteristics: "Reaction against Impressionism's naturalism", key_principles: ['Symbolic content', 'Expressive color', 'Form structure'], major_figures: ['Vincent van Gogh', 'Paul Cézanne', 'Paul Gauguin'], historical_context: 'Search for deeper meaning in art'});

CREATE (:Movement {name: 'Cubism', start_period: 1907, end_period: 1914, origin_location: 'France', characteristics: 'Fragmentation of objects into geometric forms', key_principles: ['Multiple perspectives', 'Geometric abstraction', 'Analytical deconstruction'], major_figures: ['Pablo Picasso', 'Georges Braque'], historical_context: 'Revolutionary approach to representation'});

CREATE (:Location {name: 'Florence', country: 'Italy', region: 'Tuscany', cultural_significance: 'Birthplace of Renaissance', artistic_importance: 'Center of Renaissance art and culture', notable_sites: ['Uffizi Gallery', 'Palazzo Pitti', 'Duomo']});

CREATE (:Location {name: 'Paris', country: 'France', region: 'Île-de-France', cultural_significance: 'Capital of art in 19th century', artistic_importance: 'Center of Impressionism and modern art', notable_sites: ['Louvre', "Musée d'Orsay", 'Montmartre']});

CREATE (:Location {name: 'Rome', country: 'Italy', region: 'Lazio', cultural_significance: 'Eternal city with layers of history', artistic_importance: 'Center of Baroque art and papal patronage', notable_sites: ['Vatican Museums', 'Sistine Chapel', 'Capitoline Museums']});

CREATE (:Museum {name: 'Louvre Museum', location: 'Paris', founded_year: 1793, specialization: ['European painting', 'Ancient civilizations'], notable_collections: ['Mona Lisa', 'Venus de Milo', 'Liberty Leading the People'], visitor_count: 9600000});

CREATE (:Museum {name: 'Uffizi Gallery', location: 'Florence', founded_year: 1581, specialization: ['Italian Renaissance'], notable_collections: ['Birth of Venus', 'Primavera', 'Annunciation'], visitor_count: 4400000});

CREATE (:Museum {name: 'Museum of Modern Art', location: 'New York', founded_year: 1929, specialization: ['Modern and contemporary art'], notable_collections: ['The Starry Night', "Les Demoiselles d'Avignon"], visitor_count: 3000000});

MATCH (a {name: 'Mona Lisa'})
            MATCH (b {name: 'Leonardo da Vinci'})
            CREATE (a)-[:CREATED_BY {creation_year: 1503}]->(b);

MATCH (a {name: 'The Last Supper'})
            MATCH (b {name: 'Leonardo da Vinci'})
            CREATE (a)-[:CREATED_BY {creation_year: 1495}]->(b);

MATCH (a {name: 'David'})
            MATCH (b {name: 'Michelangelo Buonarroti'})
            CREATE (a)-[:CREATED_BY {creation_year: 1504}]->(b);

MATCH (a {name: 'Water Lilies'})
            MATCH (b {name: 'Claude Monet'})
            CREATE (a)-[:CREATED_BY {creation_year: 1919}]->(b);

MATCH (a {name: 'The Starry Night'})
            MATCH (b {name: 'Vincent van Gogh'})
            CREATE (a)-[:CREATED_BY {creation_year: 1889}]->(b);

MATCH (a {name: 'Leonardo da Vinci'})
            MATCH (b {name: 'Renaissance'})
            CREATE (a)-[:BELONGS_TO_MOVEMENT {involvement_level: 'Founding figure'}]->(b);

MATCH (a {name: 'Michelangelo Buonarroti'})
            MATCH (b {name: 'Renaissance'})
            CREATE (a)-[:BELONGS_TO_MOVEMENT {involvement_level: 'Master'}]->(b);

MATCH (a {name: 'Claude Monet'})
            MATCH (b {name: 'Impressionism'})
            CREATE (a)-[:BELONGS_TO_MOVEMENT {involvement_level: 'Founder'}]->(b);

MATCH (a {name: 'Vincent van Gogh'})
            MATCH (b {name: 'Post-Impressionism'})
            CREATE (a)-[:BELONGS_TO_MOVEMENT {involvement_level: 'Key figure'}]->(b);

MATCH (a {name: 'Pablo Picasso'})
            MATCH (b {name: 'Cubism'})
            CREATE (a)-[:BELONGS_TO_MOVEMENT {involvement_level: 'Co-founder'}]->(b);

MATCH (a {name: 'Leonardo da Vinci'})
            MATCH (b {name: 'Italy'})
            CREATE (a)-[:BORN_IN {birth_year: 1452}]->(b);

MATCH (a {name: 'Claude Monet'})
            MATCH (b {name: 'Paris'})
            CREATE (a)-[:WORKED_IN {work_period: '1860-1926'}]->(b);

MATCH (a {name: 'Vincent van Gogh'})
            MATCH (b {name: 'Paris'})
            CREATE (a)-[:WORKED_IN {work_period: '1886-1888'}]->(b);

MATCH (a {name: 'Renaissance'})
            MATCH (b {name: 'Florence'})
            CREATE (a)-[:ORIGINATED_IN {origin_year: 1400}]->(b);

MATCH (a {name: 'Impressionism'})
            MATCH (b {name: 'Paris'})
            CREATE (a)-[:ORIGINATED_IN {origin_year: 1860}]->(b);

MATCH (a {name: 'Mona Lisa'})
            MATCH (b {name: 'Louvre Museum'})
            CREATE (a)-[:HOUSED_IN {acquisition_date: '1797'}]->(b);

MATCH (a {name: 'The Starry Night'})
            MATCH (b {name: 'Museum of Modern Art'})
            CREATE (a)-[:HOUSED_IN {acquisition_date: '1941'}]->(b);

MATCH (a {name: 'Pablo Picasso'})
            MATCH (b {name: 'Vincent van Gogh'})
            CREATE (a)-[:INFLUENCED_BY {influence_type: 'Color and expression'}]->(b);

MATCH (a {name: 'Claude Monet'})
            MATCH (b {name: 'Leonardo da Vinci'})
            CREATE (a)-[:INFLUENCED_BY {influence_type: 'Light studies'}]->(b);

MATCH (a {name: 'Post-Impressionism'})
            MATCH (b {name: 'Impressionism'})
            CREATE (a)-[:DEVELOPED_FROM {development_type: 'Reaction and evolution'}]->(b);

