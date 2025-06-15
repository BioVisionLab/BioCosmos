# 🦋 Biocosmos - Biodiversity Image Platform

A personalized, museum-quality biodiversity image platform that combines cutting-edge machine learning with intuitive web interfaces to explore and identify butterfly species. Built with Next.js, Python, and advanced computer vision technologies.

## 🌟 Features

### 🔍 Multi-Modal Search
- **Text Search**: Traditional species name search with autocomplete
- **Semantic Search**: Natural language queries like "orange butterfly with black lines"
- **Visual Search**: Upload an image to find visually similar species
- **Smart Search Toggle**: Seamlessly switch between search modes

### 🗺️ Interactive Visualization
- **t-SNE Map**: Explore species relationships through interactive similarity maps
- **Zoomable Interface**: Navigate through different detail levels (zoom 3-7)
- **Image Overlays**: Species images positioned by visual similarity with elegant shadows
- **Tile-Based Rendering**: Optimized performance with 256px map tiles

### 🏛️ Taxonomic Navigation
- **Hierarchical Browsing**: Navigate from Class → Order → Family → Genus → Species
- **Dynamic Routing**: Clean URLs for all taxonomic levels
- **Breadcrumb Navigation**: Always know where you are in the taxonomy
- **Representative Images**: Visual previews for each taxonomic group

### 🦋 Rich Species Information
- **Detailed Profiles**: Scientific names, common names, descriptions, conservation status
- **Image Galleries**: High-quality images with lightbox viewing
- **Geographic Maps**: Species distribution visualization
- **Taxonomic Classification**: Complete hierarchical classification

### 🤖 AI Integration
- **Intelligent Chatbot**: Ask questions about biodiversity, taxonomy, and conservation
- **CLIP Embeddings**: Advanced computer vision for semantic understanding
- **Natural Language Processing**: Powered by OpenAI's language models

### 🎨 Modern User Experience
- **Dark/Light Mode**: Automatic system preference detection with manual toggle
- **Responsive Design**: Optimized for desktop, tablet, and mobile
- **Loading States**: Smooth transitions and progress indicators
- **Error Handling**: Graceful error recovery with user-friendly messages

## 🏗️ Architecture

### Frontend Stack
- **Next.js 15**: React-based framework with App Router
- **React 19**: Latest React features with concurrent rendering
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first styling with custom theming
- **Leaflet.js**: Interactive maps for visualization
- **Lucide React**: Beautiful, customizable icons

### Backend Services
- **Python**: Machine learning and data processing
- **CLIP**: Computer vision for semantic search
- **ChromaDB**: Vector database for embeddings
- **OpenAI API**: Natural language processing
- **PIL/Pillow**: Image processing and tile generation

### Data Management
- **Static Species Data**: Curated butterfly information
- **Image Dataset**: High-quality butterfly photographs
- **Vector Embeddings**: CLIP-generated image and text embeddings
- **Tile System**: Pre-generated map tiles for visualization

## 📁 Project Structure

```
biocosmos/
├── src/
│   ├── app/                    # Next.js App Router pages
│   │   ├── api/               # API routes
│   │   ├── genus/             # Genus pages
│   │   ├── species/           # Species detail pages
│   │   ├── family/            # Family pages
│   │   ├── search/            # Search results
│   │   └── visualization/     # t-SNE map
│   ├── components/            # React components
│   │   ├── Layout.tsx         # Main app layout
│   │   ├── HeaderClient.tsx   # Navigation header
│   │   ├── ChatbotPanel.tsx   # AI assistant
│   │   └── ...               # Other components
│   └── lib/
│       └── speciesData.ts     # Species data management
├── clip_service/              # Python ML services
│   ├── create_tiles.py        # Map tile generation
│   ├── clip_search_service.py # Semantic search service
│   ├── generate_tsne_coords.py # t-SNE visualization
│   └── ...                   # Other ML scripts
├── public/
│   ├── images/               # Species image dataset
│   ├── dataset-tiles/        # Generated map tiles
│   └── ...                  # Static assets
└── unicom/                   # UNICOM model integration
```

## 🚀 Local Development Setup

### Prerequisites
- **Node.js** (v18 or higher)
- **Python** (v3.8 or higher)
- **Git**
- **OpenAI API Key** (for chatbot functionality)

### 1. Clone the Repository
```bash
git clone <repository-url>
cd biocosmos
```

### 2. Install Frontend Dependencies
```bash
npm install
# or
yarn install
```

### 3. Set Up Python Environment
```bash
cd clip_service
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt  # You may need to create this file
```

### 4. Install Python Dependencies
```bash
pip install pillow numpy scikit-learn chromadb openai clip-by-openai torch torchvision
```

### 5. Environment Configuration
Create a `.env.local` file in the root directory:
```env
OPENAI_API_KEY=your_openai_api_key_here
CLIP_SERVICE_URL=http://localhost:5001
```

### 6. Prepare the Dataset
Ensure your butterfly images are organized in:
```
public/images/nymphalidae_new/
├── species_folder_1/
│   ├── image1.jpg
│   └── image2.jpg
└── species_folder_2/
    ├── image1.jpg
    └── image2.jpg
```

### 7. Generate Embeddings and Tiles
```bash
cd clip_service
python embed_images.py          # Generate CLIP embeddings
python generate_tsne_coords.py  # Create t-SNE coordinates
python create_tiles.py          # Generate map tiles
```

### 8. Start the Services

**Terminal 1 - Frontend:**
```bash
npm run dev
```

**Terminal 2 - CLIP Service:**
```bash
cd clip_service
python clip_search_service.py
```

### 9. Access the Application
Open [http://localhost:3000](http://localhost:3000) in your browser.

## 🔧 Configuration

### Tile Generation Settings
Edit `clip_service/create_tiles.py`:
```python
TILE_SIZE = 256              # Tile dimensions
IMAGE_SIZE_ON_TILE = 128     # Species image size
MAX_ZOOM = 7                 # Maximum zoom level
SHADOW_RADIUS = 4            # Image shadow effect
```

### Search Configuration
Modify search behavior in `src/components/HeaderClient.tsx`:
- Adjust semantic search parameters
- Customize search result handling
- Configure error messages

### Visualization Settings
Update map settings in `src/components/VisualizationMapClient.tsx`:
- Change zoom levels and bounds
- Modify tile URL patterns
- Adjust map center and initial view

## 🐛 Known Issues & Troubleshooting

### Tile 404 Errors
If you see 404 errors for tiles with negative coordinates:
1. Check tile generation bounds in `create_tiles.py`
2. Verify coordinate normalization settings
3. Ensure map center matches tile coordinate system

### Search Not Working
1. Verify CLIP service is running on port 5001
2. Check OpenAI API key configuration
3. Ensure embeddings are generated correctly

### Images Not Loading
1. Verify image paths in `public/images/nymphalidae_new/`
2. Check file permissions
3. Ensure image formats are supported (JPEG, PNG)

## 📊 Performance Optimization

### Image Optimization
- Use Next.js Image component for automatic optimization
- Generate multiple image sizes for responsive design
- Implement lazy loading for large galleries

### Tile Caching
- Pre-generate tiles for all zoom levels
- Implement tile caching strategies
- Use CDN for tile delivery in production

### Search Performance
- Index embeddings for faster similarity search
- Implement search result caching
- Use pagination for large result sets

## 🚀 Production Deployment

### Vercel Deployment (Recommended)
1. Connect your GitHub repository to Vercel
2. Configure environment variables in Vercel dashboard
3. Deploy with automatic CI/CD

### Docker Deployment
```dockerfile
# Example Dockerfile structure
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

### Server Requirements
- **CPU**: Multi-core for tile generation and ML processing
- **RAM**: 8GB+ for CLIP model and embeddings
- **Storage**: SSD recommended for image dataset
- **Network**: High bandwidth for image serving

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **iNaturalist**: Inspiration for biodiversity platforms
- **OpenAI CLIP**: Computer vision capabilities
- **Leaflet**: Interactive mapping functionality
- **Next.js Team**: Excellent React framework
- **Butterfly Dataset Contributors**: High-quality species images

## 📞 Support

For questions, issues, or contributions:
- Open an issue on GitHub
- Check the troubleshooting section above
- Review the configuration options

---

**Biocosmos** - Exploring biodiversity through the lens of AI 🦋✨
