MATCH (n) DETACH DELETE n;

MATCH (n) DETACH DELETE n;

CREATE CONSTRAINT artist_name_unique IF NOT EXISTS FOR (n:Artist) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT painting_name_unique IF NOT EXISTS FOR (n:Painting) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT museum_name_unique IF NOT EXISTS FOR (n:Museum) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT movement_name_unique IF NOT EXISTS FOR (n:Movement) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT exhibition_name_unique IF NOT EXISTS FOR (n:Exhibition) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT technique_name_unique IF NOT EXISTS FOR (n:Technique) REQUIRE n.name IS UNIQUE;

CREATE INDEX artist_name_index IF NOT EXISTS FOR (n:Artist) ON (n.name);

CREATE INDEX artist_title_index IF NOT EXISTS FOR (n:Artist) ON (n.title);

CREATE INDEX artist_creation_date_index IF NOT EXISTS FOR (n:Artist) ON (n.creation_date);

CREATE INDEX artist_birth_year_index IF NOT EXISTS FOR (n:Artist) ON (n.birth_year);

CREATE INDEX artist_death_year_index IF NOT EXISTS FOR (n:Artist) ON (n.death_year);

CREATE INDEX artist_location_index IF NOT EXISTS FOR (n:Artist) ON (n.location);

CREATE INDEX painting_name_index IF NOT EXISTS FOR (n:Painting) ON (n.name);

CREATE INDEX painting_title_index IF NOT EXISTS FOR (n:Painting) ON (n.title);

CREATE INDEX painting_creation_date_index IF NOT EXISTS FOR (n:Painting) ON (n.creation_date);

CREATE INDEX painting_birth_year_index IF NOT EXISTS FOR (n:Painting) ON (n.birth_year);

CREATE INDEX painting_death_year_index IF NOT EXISTS FOR (n:Painting) ON (n.death_year);

CREATE INDEX painting_location_index IF NOT EXISTS FOR (n:Painting) ON (n.location);

CREATE INDEX museum_name_index IF NOT EXISTS FOR (n:Museum) ON (n.name);

CREATE INDEX museum_title_index IF NOT EXISTS FOR (n:Museum) ON (n.title);

CREATE INDEX museum_creation_date_index IF NOT EXISTS FOR (n:Museum) ON (n.creation_date);

CREATE INDEX museum_birth_year_index IF NOT EXISTS FOR (n:Museum) ON (n.birth_year);

CREATE INDEX museum_death_year_index IF NOT EXISTS FOR (n:Museum) ON (n.death_year);

CREATE INDEX museum_location_index IF NOT EXISTS FOR (n:Museum) ON (n.location);

CREATE INDEX movement_name_index IF NOT EXISTS FOR (n:Movement) ON (n.name);

CREATE INDEX movement_title_index IF NOT EXISTS FOR (n:Movement) ON (n.title);

CREATE INDEX movement_creation_date_index IF NOT EXISTS FOR (n:Movement) ON (n.creation_date);

CREATE INDEX movement_birth_year_index IF NOT EXISTS FOR (n:Movement) ON (n.birth_year);

CREATE INDEX movement_death_year_index IF NOT EXISTS FOR (n:Movement) ON (n.death_year);

CREATE INDEX movement_location_index IF NOT EXISTS FOR (n:Movement) ON (n.location);

CREATE INDEX exhibition_name_index IF NOT EXISTS FOR (n:Exhibition) ON (n.name);

CREATE INDEX exhibition_title_index IF NOT EXISTS FOR (n:Exhibition) ON (n.title);

CREATE INDEX exhibition_creation_date_index IF NOT EXISTS FOR (n:Exhibition) ON (n.creation_date);

CREATE INDEX exhibition_birth_year_index IF NOT EXISTS FOR (n:Exhibition) ON (n.birth_year);

CREATE INDEX exhibition_death_year_index IF NOT EXISTS FOR (n:Exhibition) ON (n.death_year);

CREATE INDEX exhibition_location_index IF NOT EXISTS FOR (n:Exhibition) ON (n.location);

CREATE INDEX technique_name_index IF NOT EXISTS FOR (n:Technique) ON (n.name);

CREATE INDEX technique_title_index IF NOT EXISTS FOR (n:Technique) ON (n.title);

CREATE INDEX technique_creation_date_index IF NOT EXISTS FOR (n:Technique) ON (n.creation_date);

CREATE INDEX technique_birth_year_index IF NOT EXISTS FOR (n:Technique) ON (n.birth_year);

CREATE INDEX technique_death_year_index IF NOT EXISTS FOR (n:Technique) ON (n.death_year);

CREATE INDEX technique_location_index IF NOT EXISTS FOR (n:Technique) ON (n.location);

CREATE (:Artist {name: 'Leonardo da Vinci', full_name: 'Leonardo di ser Piero da Vinci', birth_year: 1452, death_year: 1519, birth_place: 'Vinci, Republic of Florence', death_place: 'Amboise, Kingdom of France', nationality: 'Italian', gender: 'Male', biography: 'Renaissance polymath: painter, scientist, engineer, inventor, anatomist', education: ["Andrea del Verrocchio's workshop"], teachers: ['Andrea del Verrocchio'], students: ['Francesco Melzi', 'Gian Giacomo Caprotti'], art_movements: ['High Renaissance', 'Renaissance'], periods: ['Early Renaissance', 'High Renaissance'], primary_medium: ['Oil painting', 'Drawing', 'Fresco'], signature_techniques: ['Sfumato', 'Chiaroscuro', 'Anatomical accuracy'], notable_works: ['Mona Lisa', 'The Last Supper', 'Vitruvian Man', 'Lady with an Ermine'], awards_honors: ['Court artist to Francis I of France'], exhibitions: ['Leonardo da Vinci: Painter at the Court of Milan'], collections: ['Louvre', 'National Gallery London', 'Uffizi'], artistic_evolution: 'From traditional workshop training to revolutionary innovations', historical_significance: 'Epitome of Renaissance universal genius', market_value_trend: 'Priceless - most valuable artworks in history', social_background: 'Illegitimate son of notary, rose through talent', family_connections: ['Ser Piero da Vinci (father)'], workshop_location: 'Milan, Florence, France', patrons: ['Ludovico Sforza', 'Francis I of France', 'Cesare Borgia'], influences: ['Classical antiquity', 'Nature observation', 'Verrocchio'], legacy: 'Scientific method in art, perfectionism, interdisciplinary approach'});

CREATE (:Artist {name: 'Claude Monet', full_name: 'Oscar-Claude Monet', birth_year: 1840, death_year: 1926, birth_place: 'Paris, France', death_place: 'Giverny, France', nationality: 'French', gender: 'Male', biography: 'Founder and leading figure of Impressionism', education: ['École des Beaux-Arts (briefly)', 'Self-taught'], teachers: ['Eugène Boudin', 'Johan Jongkind'], students: ['Blanche Hoschedé-Monet'], art_movements: ['Impressionism'], periods: ['Late 19th century', 'Early 20th century'], primary_medium: ['Oil painting', 'Pastels'], signature_techniques: ['Plein air painting', 'Broken color', 'Light studies'], notable_works: ['Water Lilies', 'Impression, Sunrise', 'Rouen Cathedral', 'Haystacks'], exhibitions: ['First Impressionist Exhibition 1874', 'Salon des Indépendants'], collections: ['Musée Marmottan', 'Metropolitan Museum', 'National Gallery London'], artistic_evolution: 'From landscape realism to light abstraction', historical_significance: 'Revolutionized modern painting through light studies', workshop_location: 'Giverny gardens', patrons: ['Paul Durand-Ruel', 'Gustave Caillebotte'], influences: ['Eugène Boudin', 'Japanese prints', 'Turner'], legacy: 'Foundation of modern art through Impressionism'});

CREATE (:Artist {name: 'Frida Kahlo', full_name: 'Magdalena Carmen Frida Kahlo y Calderón', birth_year: 1907, death_year: 1954, birth_place: 'Coyoacán, Mexico City', death_place: 'Coyoacán, Mexico City', nationality: 'Mexican', gender: 'Female', biography: 'Surrealist painter known for self-portraits and Mexican culture', education: ['Self-taught'], art_movements: ['Surrealism', 'Mexican Muralism', 'Mexicanidad'], periods: ['20th century modernism'], primary_medium: ['Oil painting', 'Mixed media'], signature_techniques: ['Symbolic self-portraiture', 'Mexican folk art elements'], notable_works: ['The Two Fridas', 'Self-Portrait with Thorn Necklace', 'The Broken Column'], exhibitions: ['First solo exhibition 1953', 'Posthumous international recognition'], historical_significance: 'Icon of Mexican identity and feminist art', social_background: 'Middle-class Mexican family, political activism', patrons: ['Diego Rivera', 'André Breton'], influences: ['Mexican folk art', 'Pre-Columbian art', 'European Surrealism'], legacy: 'Feminist icon, Mexican cultural ambassador through art'});

CREATE (:Painting {title: 'Mona Lisa', alternative_titles: ['La Gioconda', 'La Joconde'], creation_date: '1503-1519', completion_date: '1519', artist: 'Leonardo da Vinci', dimensions: '77 cm × 53 cm (30 in × 21 in)', medium: 'Oil', support: 'Poplar wood panel', technique: ['Sfumato', 'Chiaroscuro', 'Oil glazing'], style: 'High Renaissance', genre: 'Portrait', subject_matter: ['Portrait', 'Landscape background'], description: 'Portrait of Lisa Gherardini with enigmatic smile and atmospheric landscape', iconography: ['Enigmatic smile', 'Hands placement', 'Veil', 'Landscape'], composition: 'Three-quarter view with pyramidal composition', color_palette: ['Earth tones', 'Subtle greens', 'Warm flesh tones'], condition: 'Good with minor cracking', provenance: ['Francis I of France', 'French Royal Collection', 'Louvre acquisition 1797'], exhibitions: ['Permanent display Louvre', 'Rare loans to other museums'], publications: ['Countless scholarly articles', 'Popular culture references'], current_location: 'Louvre Museum, Paris', insurance_value: 'Priceless', market_value: 'Estimated over $1 billion', signature: False, inscription: 'None visible', frame: 'Modern protective case', historical_context: 'Renaissance humanism and portraiture innovation', cultural_significance: 'Global icon of art and culture', technical_analysis: 'X-ray reveals under-drawings and painting process', conservation_history: ['1911 theft recovery', 'Modern climate control', 'Protective glass'], related_works: ['Lady with an Ermine', "Portrait of Ginevra de' Benci"]});

CREATE (:Painting {title: 'Water Lilies (Nymphéas)', alternative_titles: ['Les Nymphéas', 'Water Lily Pond'], creation_date: '1897-1926', completion_date: 'Various dates - series', artist: 'Claude Monet', dimensions: 'Various sizes - largest 2m x 6m', medium: 'Oil', support: 'Canvas', technique: ['Plein air painting', 'Broken brushwork', 'Color layering'], style: 'Impressionism', genre: 'Landscape', subject_matter: ['Water garden', 'Light reflections', 'Natural abstraction'], description: "Series of paintings of Monet\\'s water garden at Giverny", iconography: ['Water lilies', 'Bridge', 'Weeping willows', 'Light reflections'], composition: 'Horizontal panoramic views, some without horizon line', color_palette: ['Blues', 'Greens', 'Purples', 'Yellow highlights'], condition: 'Varies by individual painting', provenance: ["Artist's estate", 'Various museums and private collections'], exhibitions: ['Orangerie installation', 'Major Monet retrospectives'], current_location: 'Multiple museums worldwide', historical_context: 'Late Impressionism and abstraction development', cultural_significance: 'Bridge between Impressionism and abstract art', related_works: ['Japanese Bridge series', 'Rouen Cathedral series']});

CREATE (:Museum {name: 'Louvre Museum', full_name: 'Musée du Louvre', location: 'Rue de Rivoli, Paris', city: 'Paris', country: 'France', founded_year: 1793, founder: 'French Republic', museum_type: 'National art museum', specialization: ['European painting', 'Ancient civilizations', 'Decorative arts'], collection_size: 380000, permanent_collection: ['Mona Lisa', 'Venus de Milo', 'Winged Victory'], notable_works: ['Mona Lisa', 'Liberty Leading the People', 'Wedding at Cana'], annual_visitors: 9600000, director: 'Laurence des Cars', curators: ['Department curators for each collection'], building_architect: 'Pierre Lescot, I.M. Pei (pyramid)', building_style: 'French Renaissance with modern additions', website: 'www.louvre.fr', opening_hours: '9 AM - 6 PM (varies by day)', admission_policy: 'Paid admission with exceptions', educational_programs: ['School programs', 'Adult courses', 'Audio guides'], research_facilities: True, conservation_lab: True, library: True, gift_shop: True, restaurant: True, accessibility: ['Wheelchair access', 'Audio descriptions', 'Touch tours'], partnerships: ['International museum loans', 'Academic collaborations'], funding_sources: ['French government', 'Admissions', 'Donations', 'Sponsorships'], mission_statement: 'Preserve and present art heritage for public education', acquisition_policy: 'Strategic acquisitions filling collection gaps', deaccession_policy: 'Rarely deaccessions due to national treasure status'});

CREATE (:Museum {name: 'Museum of Modern Art', full_name: 'The Museum of Modern Art', location: '11 West 53rd Street, Manhattan', city: 'New York', country: 'United States', founded_year: 1929, founder: 'Group of influential patrons led by Abby Aldrich Rockefeller', museum_type: 'Modern and contemporary art museum', specialization: ['Modern art', 'Contemporary art', 'Design', 'Film'], collection_size: 200000, permanent_collection: ['The Starry Night', "Les Demoiselles d'Avignon", "Campbell's Soup Cans"], notable_works: ['The Starry Night', 'The Persistence of Memory', 'Broadway Boogie-Woogie'], annual_visitors: 3000000, director: 'Glenn D. Lowry', building_architect: 'Yoshio Taniguchi (2004 renovation)', building_style: 'Modern architecture', website: 'www.moma.org', educational_programs: ['MoMA Learning', 'Teacher programs', 'Family programs'], research_facilities: True, conservation_lab: True, library: True, mission_statement: 'Help people understand and enjoy modern and contemporary art'});

CREATE (:Exhibition {title: 'Leonardo da Vinci: Painter at the Court of Milan', subtitle: 'Complete paintings and drawings', venue: 'National Gallery, London', start_date: '2011-11-09', end_date: '2012-02-05', duration: 88, exhibition_type: 'Monographic retrospective', curator: ['Luke Syson', 'Larry Keith'], organizer: 'National Gallery London', sponsor: ['Credit Suisse', 'Ernst & Young'], theme: "Leonardo\\'s painting practice and technique", concept: "First exhibition to unite Leonardo\\'s surviving paintings", featured_artists: ['Leonardo da Vinci'], artworks: ['Lady with an Ermine', 'Salvator Mundi', 'The Virgin of the Rocks'], number_of_works: 65, catalog: 'Comprehensive scholarly catalog', catalog_authors: ['Luke Syson', 'Larry Keith', 'Ashok Roy'], visitor_count: 324000, reviews: ['Five stars Guardian', 'Exceptional Times review'], press_coverage: ['International media attention', 'Documentary films'], educational_programs: ['Lectures', 'Drawing workshops', 'School visits'], lectures: ['Technical analysis talks', 'Renaissance context lectures'], guided_tours: True, audio_guide: True, multimedia: ['Interactive displays', 'Digital reconstructions'], significance: 'Unprecedented gathering of Leonardo paintings', innovations: ['Advanced technical analysis display', 'Digital x-ray presentations']});

CREATE (:Technique {name: 'Sfumato', alternative_names: ['Sfumare', 'Smoky technique'], category: 'Painting technique', description: 'Subtle gradations of tone without harsh outlines', origin_period: 'High Renaissance', origin_location: 'Italy', inventor: 'Leonardo da Vinci', development_history: "Evolved from Leonardo\\'s anatomical and optical studies", materials_required: ['Oil paints', 'Multiple glazes', 'Fine brushes'], tools_required: ['Soft brushes', 'Palette knife', 'Glazing medium'], process_steps: ['Underpainting', 'Multiple glaze layers', 'Subtle blending'], difficulty_level: 'Expert', time_required: 'Months to years', notable_practitioners: ['Leonardo da Vinci', 'Correggio', 'Later followers'], masterpieces_using: ['Mona Lisa', 'Lady with an Ermine', 'The Virgin of the Rocks'], variations: ['Venetian sfumato', 'Northern European adaptations'], related_techniques: ['Chiaroscuro', 'Glazing', 'Impasto'], advantages: ['Atmospheric effects', 'Psychological depth', 'Luminous quality'], limitations: ['Time-intensive', 'Requires expert skill', 'Fragile layers'], preservation_concerns: ['Layer separation', 'Darkening glazes'], modern_adaptations: ['Digital sfumato effects', 'Contemporary oil techniques'], teaching_traditions: ['Academic art education', 'Classical ateliers'], cultural_significance: 'Epitome of Renaissance painting sophistication'});

CREATE (:Critic {name: 'John Ruskin', full_name: 'John Ruskin', birth_year: 1819, death_year: 1900, nationality: 'British', specialization: ['Art criticism', 'Social criticism', 'Architecture'], major_works: ['Modern Painters', 'The Stones of Venice'], influence: 'Champion of Turner and Pre-Raphaelites', writing_style: 'Detailed aesthetic analysis with moral philosophy'});

CREATE (:Curator {name: 'Harald Szeemann', birth_year: 1933, death_year: 2005, nationality: 'Swiss', specialization: ['Contemporary art', 'Avant-garde movements'], major_exhibitions: ['When Attitudes Become Form', 'Documenta 5'], curatorial_philosophy: 'Art as research and experimentation', institutions: ['Kunsthalle Bern', 'Independent curator']});

MATCH (a {name: 'Mona Lisa'})
            MATCH (b {name: 'Leonardo da Vinci'})
            CREATE (a)-[:CREATED_BY {creation_year: 1503, creation_location: 'Florence/France', commission_type: 'Portrait commission', attribution_certainty: 1.0}]->(b);

MATCH (a {name: 'Water Lilies (Nymphéas)'})
            MATCH (b {name: 'Claude Monet'})
            CREATE (a)-[:CREATED_BY {creation_year: 1919, creation_location: 'Giverny', commission_type: 'Personal project', attribution_certainty: 1.0}]->(b);

MATCH (a {name: 'Mona Lisa'})
            MATCH (b {name: 'Sfumato'})
            CREATE (a)-[:USES_TECHNIQUE {skill_level: 'Master', innovation: 'Perfected the technique'}]->(b);

MATCH (a {name: 'Mona Lisa'})
            MATCH (b {name: 'Louvre Museum'})
            CREATE (a)-[:HOUSED_IN {acquisition_date: '1797', display_status: 'Permanent display'}]->(b);

MATCH (a {name: 'Water Lilies (Nymphéas)'})
            MATCH (b {name: 'Museum of Modern Art'})
            CREATE (a)-[:HOUSED_IN {acquisition_date: 'Various', display_status: 'Rotating display'}]->(b);

MATCH (a {name: 'Mona Lisa'})
            MATCH (b {name: 'Leonardo da Vinci: Painter at the Court of Milan'})
            CREATE (a)-[:EXHIBITED_AT {exhibition_title: 'Leonardo da Vinci: Painter at the Court of Milan', date: '2011-2012', venue: 'National Gallery London', role: 'Featured work', significance: 'Rare loan'}]->(b);

MATCH (a {name: 'Claude Monet'})
            MATCH (b {name: 'Leonardo da Vinci'})
            CREATE (a)-[:INFLUENCED_BY {influence_type: 'Light studies and atmospheric effects', evidence: "Documented in Monet's writings", period: '1860s onwards', degree: 0.7, specific_aspects: ['Light observation', 'Atmospheric perspective']}]->(b);

MATCH (a {name: 'Leonardo da Vinci'})
            MATCH (b {name: 'Italy'})
            CREATE (a)-[:BORN_IN {birth_year: 1452}]->(b);

MATCH (a {name: 'Leonardo da Vinci'})
            MATCH (b {name: 'France'})
            CREATE (a)-[:WORKED_IN {work_period: '1516-1519', major_works_created: ['Late period works']}]->(b);

MATCH (a {name: 'Claude Monet'})
            MATCH (b {name: 'France'})
            CREATE (a)-[:WORKED_IN {work_period: '1840-1926', major_works_created: ['Impression Sunrise', 'Water Lilies']}]->(b);

MATCH (a {name: 'Louvre Museum'})
            MATCH (b {name: 'Paris'})
            CREATE (a)-[:CREATED_IN {}]->(b);

MATCH (a {name: 'Museum of Modern Art'})
            MATCH (b {name: 'New York'})
            CREATE (a)-[:CREATED_IN {}]->(b);

MATCH (a {name: 'Leonardo da Vinci'})
            MATCH (b {name: 'John Ruskin'})
            CREATE (a)-[:CRITIQUED_BY {criticism_type: 'Historical analysis', publication: 'Modern Painters', assessment: 'Praise for naturalistic observation'}]->(b);

MATCH (a {name: 'Leonardo da Vinci: Painter at the Court of Milan'})
            MATCH (b {name: 'Luke Syson'})
            CREATE (a)-[:CREATED_BY {curatorial_approach: 'Technical and historical analysis', exhibition_concept: 'Complete painting oeuvre'}]->(b);

