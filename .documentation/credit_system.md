# MakeIt3D Credit System & Pricing

## Credit Economics

- **Base Rate**: 1 MakeIt3D Credit = $0.03
- **Free Tier**: 30 credits per user ($0.90 value)
- **Target Margin**: ~2-3x markup on API costs for sustainability

## Operation Pricing Table

| Operation | Provider | API Cost (USD) | MakeIt3D Credits | MakeIt3D Cost (USD) | Markup |
|-----------|----------|----------------|------------------|---------------------|--------|
| **2D Image Generation** | | | | | |
| Text-to-Image (Core) | Stability | $0.03 | 2 | $0.06 | 2x |
| Text-to-Image (Ultra) | Stability | $0.08 | 3 | $0.09 | 1.1x |
| Text-to-Image (V3) | Recraft | $0.04 | 2 | $0.06 | 1.5x |
| Text-to-Image (V2) | Recraft | $0.022 | 1 | $0.03 | 1.4x |
| Image-to-Image | Stability | $0.03 | 2 | $0.06 | 2x |
| Image-to-Image | Recraft | $0.04 | 2 | $0.06 | 1.5x |
| **2D Image Enhancement** | | | | | |
| Remove Background | Stability | $0.02 | 1 | $0.03 | 1.5x |
| Remove Background | Recraft | $0.01 | 1 | $0.03 | 3x |
| Search & Recolor | Stability | $0.05 | 2 | $0.06 | 1.2x |
| Image Inpaint | Recraft | $0.04 | 2 | $0.06 | 1.5x |
| Sketch-to-Image | Stability | $0.03 | 2 | $0.06 | 2x |
| **3D Model Generation** | | | | | |
| Text-to-3D Model | Tripo | ~$0.20* | 8 | $0.24 | 1.2x |
| Image-to-3D Model (Single) | Tripo | ~$0.25* | 10 | $0.30 | 1.2x |
| Image-to-3D Model (Multi-view) | Tripo | ~$0.35* | 12 | $0.36 | 1.03x |
| Image-to-3D Model | Stability | $0.04 | 3 | $0.09 | 2.25x |
| Refine 3D Model | Tripo | ~$0.15* | 6 | $0.18 | 1.2x |

*Estimated Tripo costs based on industry standards and complexity

## Subscription Tiers

| Tier | Monthly Cost | Credits Included | Extra Credit Cost | Target Users |
|------|-------------|------------------|-------------------|--------------|
| **Free** | $0 | 30 | $0.05/credit | Casual users |
| **Hobbyist** | $9.99 | 400 | $0.04/credit | Regular creators |
| **Creator** | $29.99 | 1,200 | $0.035/credit | Professional users |
| **Studio** | $99.99 | 4,500 | $0.03/credit | Teams & agencies |

## Free Tier Analysis

**30 Free Credits Usage Examples:**
- 15 text-to-image generations (Stability Core)
- 3 complete 3D models from images
- 30 background removals
- Mix: 2 3D models (20 credits) + 5 image generations (10 credits)

**Cost to MakeIt3D**: ~$0.60-0.90 per free user
**Customer Acquisition Value**: Reasonable for freemium model

## Implementation Status ✅

### Database Schema (Implemented)
- ✅ `user_credits` table with balance and subscription tracking
- ✅ `credit_transactions` table for audit trail
- ✅ `operation_costs` table for configurable pricing
- ✅ All indexes and relationships configured
- ✅ Pre-populated with current operation costs

### BFF Integration (Implemented)
- ✅ Credit management functions in `supabase_handler.py`
- ✅ Automatic user initialization with 30 free credits
- ✅ Credit checking and deduction before API calls
- ✅ Transaction logging for audit and analytics
- ✅ Credit history retrieval for user dashboard

### API Integration Pattern

```python
# Before making any AI API call:
credit_result = await check_and_deduct_credits(
    user_id=user_id,
    operation_key="text_to_image_stability_core",
    task_id=task_id
)

# Proceed with AI API call only if credits were successfully deducted
if credit_result["success"]:
    # Make AI API call
    result = await ai_provider.generate_image(...)
```

### Operation Keys Reference

| Operation Key | Description |
|---------------|-------------|
| `text_to_image_core` | Core text-to-image generation |
| `text_to_image_ultra` | Ultra quality text-to-image generation |
| `text_to_image_v3` | V3 text-to-image generation |
| `text_to_image_v2` | V2 text-to-image generation |
| `image_to_image` | Image-to-image transformation |
| `remove_background` | Background removal service |
| `search_recolor` | Search and recolor functionality |
| `image_to_3d` | 3D model generation |

### Next Steps (Not Implemented Yet)
- [ ] Add credit endpoints to main router (`/api/credits/*`)
- [ ] Update existing AI endpoints to use credit system
- [ ] Add subscription management endpoints
- [ ] Add credit purchase/payment integration
- [ ] Frontend credit display and management UI
- [ ] Admin dashboard for cost monitoring

## 🔒 CONFIDENTIAL: Complete Operation Details (Temporarily Hidden from Consultant)

**Note**: The 3D generation operations, Tripo provider details, and all real provider names (Stability, Recraft) have been temporarily obfuscated in the database `operation_costs` table. The consultant will only see generic "provider_a" and "provider_b" names. The complete details are preserved here for later restoration.

### Complete Original Operation Costs (Full Details)

| Operation Key | Operation Name | Provider | Credits | API Cost (USD) | Status |
|---------------|----------------|----------|---------|---------------|--------|
| `text_to_image_recraft_v2` | Text-to-Image (Recraft V2) | **recraft** | 1 | $0.022 | ✅ Active (as provider_b) |
| `text_to_image_recraft_v3`